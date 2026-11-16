import os
import re
import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import pymupdf as fitz
from PIL import Image

from app.config import settings
from app.db.groq_client import groq_wrapper

logger = logging.getLogger(__name__)

ADMIN_PAGE_PATTERNS = [
    r'certify\s+that',
    r'bonafide\s+record',
    r'acknowledgments?\s*\n\s*the\s+successful',
    r'heartfelt\s+gratitude',
    r'index\s*\n+\s*sl\s+no',
    r'references\s+and\s+case\s+study\s+sources',
    r'submitted\s+in\s+partial\s+fulfillment',
    r'under\s+the\s+guidance\s+of',
]

def is_admin_page(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in ADMIN_PAGE_PATTERNS)

def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[Dict[str, Any]]:
    """Splits text into overlapping chunks respecting sentence and word boundaries."""
    text = text.strip()
    if not text:
        return []
    
    if len(text) <= chunk_size:
        return [{"content": text, "start": 0, "end": len(text)}]

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    curr_sentences = []
    curr_len = 0
    start_pos = 0

    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        if curr_len + len(s) > chunk_size and curr_sentences:
            content_str = " ".join(curr_sentences)
            end_pos = start_pos + len(content_str)
            chunks.append({
                "content": content_str,
                "start": start_pos,
                "end": end_pos
            })
            # Always carry over the last 1 or 2 sentences as overlap
            overlap_sents = curr_sentences[-2:] if len(curr_sentences) >= 2 else curr_sentences[-1:]
            curr_sentences = list(overlap_sents) + [s]
            curr_len = sum(len(x) for x in curr_sentences)
            start_pos = max(0, end_pos - sum(len(x) for x in overlap_sents))
        else:
            curr_sentences.append(s)
            curr_len += len(s)

    if curr_sentences:
        content_str = " ".join(curr_sentences)
        chunks.append({
            "content": content_str,
            "start": start_pos,
            "end": start_pos + len(content_str)
        })

    return chunks

def ingest_document(
    file_path: str,
    source_id: Optional[str] = None,
    chunk_size: int = 900,
    overlap: int = 120
) -> List[Dict[str, Any]]:
    """Ingests PDF or plain text document using PyMuPDF and produces structured chunks."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found at {file_path}")

    sid = source_id or path.stem
    chunks: List[Dict[str, Any]] = []

    if path.suffix.lower() == ".pdf":
        doc = fitz.open(str(path))
        chunk_idx = 0
        for page_idx, page in enumerate(doc, start=1):
            page_text = page.get_text()
            # If text is empty or minimal (e.g. scanned page or image presentation), run OCR fallback
            if len(page_text.strip()) < 20:
                try:
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    ocr_res = extract_ocr_from_image_or_array(img_bytes)
                    if ocr_res.strip():
                        page_text = ocr_res.strip()
                except Exception as e:
                    logger.debug(f"OCR fallback on PDF page {page_idx} skipped: {e}")

            if not page_text.strip():
                continue
            if is_admin_page(page_text):
                logger.info(f"Skipping administrative page {page_idx} ({sid})")
                continue
            page_chunks = chunk_text(page_text, chunk_size=chunk_size, overlap=overlap)
            for pc in page_chunks:
                chunk_id = f"{sid}_doc_p{page_idx}_c{chunk_idx}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "source_id": sid,
                    "modality": "document",
                    "page_num": page_idx,
                    "content": pc["content"],
                    "metadata": {
                        "source_id": sid,
                        "modality": "document",
                        "page_num": page_idx,
                        "char_start": pc["start"],
                        "char_end": pc["end"],
                        "file_name": path.name
                    }
                })
                chunk_idx += 1
        doc.close()
    else:
        # Plain text
        with open(str(path), "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()
        text_chunks = chunk_text(full_text, chunk_size=chunk_size, overlap=overlap)
        for idx, tc in enumerate(text_chunks):
            chunk_id = f"{sid}_doc_p1_c{idx}"
            chunks.append({
                "chunk_id": chunk_id,
                "source_id": sid,
                "modality": "document",
                "page_num": 1,
                "content": tc["content"],
                "metadata": {
                    "source_id": sid,
                    "modality": "document",
                    "page_num": 1,
                    "char_start": tc["start"],
                    "char_end": tc["end"],
                    "file_name": path.name
                }
            })

    logger.info(f"Ingested document {path.name}: produced {len(chunks)} chunks.")
    return chunks

def ingest_audio(file_path: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Ingests audio file (.mp3, .wav) with timestamped segments using Groq Whisper or fallback."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found at {file_path}")

    sid = source_id or path.stem

    # Check for companion transcript JSON first if offline or fallback
    companion_json = path.with_suffix(".json")
    if companion_json.exists():
        try:
            import json
            with open(companion_json, "r", encoding="utf-8") as f:
                transcription = json.load(f)
        except Exception:
            transcription = groq_wrapper.transcribe_audio(str(path))
    else:
        transcription = groq_wrapper.transcribe_audio(str(path))
    
    segments = transcription.get("segments", [])
    chunks: List[Dict[str, Any]] = []

    if not segments and transcription.get("text"):
        # Single segment if no fine-grained breakdown
        chunks.append({
            "chunk_id": f"{sid}_aud_0",
            "source_id": sid,
            "modality": "audio",
            "content": transcription["text"].strip(),
            "start_time": 0.0,
            "end_time": float(transcription.get("duration", 0.0)),
            "metadata": {
                "source_id": sid,
                "modality": "audio",
                "start_time": 0.0,
                "end_time": float(transcription.get("duration", 0.0)),
                "file_name": path.name
            }
        })
    else:
        for idx, seg in enumerate(segments):
            seg_text = seg.get("text", "").strip()
            if not seg_text:
                continue
            chunk_id = f"{sid}_aud_{idx}"
            start_t = float(seg.get("start", 0.0))
            end_t = float(seg.get("end", 0.0))
            chunks.append({
                "chunk_id": chunk_id,
                "source_id": sid,
                "modality": "audio",
                "content": seg_text,
                "start_time": start_t,
                "end_time": end_t,
                "metadata": {
                    "source_id": sid,
                    "modality": "audio",
                    "start_time": start_t,
                    "end_time": end_t,
                    "file_name": path.name
                }
            })

    logger.info(f"Ingested audio {path.name}: produced {len(chunks)} timestamped chunks.")
    return chunks

def separate_joined_words(text: str) -> str:
    """Inserts spaces in camelCase or joined punctuation tokens for readability."""
    import re
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([:,;&])([A-Za-z0-9])', r'\1 \2', text)
    return text

def extract_ocr_from_image_or_array(img_source) -> str:
    """Extracts text using rapidocr-onnxruntime, cleaning noise and merging label pairs."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        res, _ = engine(img_source)
        if not res:
            return ""

        raw_lines = [separate_joined_words(line[1].strip()) for line in res if line and len(line) > 1 and len(line[1].strip()) > 1]
        
        # Merge label headers with their values if on consecutive lines
        merged_lines = []
        i = 0
        known_labels = {
            "generalevaluator": "General Evaluator",
            "toastmasteroftheday": "Toastmaster of the Day",
            "awards&recognitions": "Awards & Recognitions",
            "sergeantatarms": "Sergeant at Arms",
            "executivecommittee": "Executive Committee",
            "vppublicrelations": "VP Public Relations",
            "president": "President",
            "secretary": "Secretary",
            "treasurer": "Treasurer"
        }
        
        while i < len(raw_lines):
            curr = raw_lines[i]
            curr_clean = curr.replace(" ", "").lower().rstrip(":")
            
            # If current line is a known label or ends with colon, check next line
            if (curr.endswith(":") or curr_clean in known_labels) and i + 1 < len(raw_lines):
                next_l = raw_lines[i+1]
                if not next_l.endswith(":"):
                    label = known_labels.get(curr_clean, curr.rstrip(":"))
                    merged_lines.append(f"{label}: {next_l}")
                    i += 2
                    continue
            
            # Format known single-word role prefixes
            matched_prefix = False
            for k_prefix, k_name in known_labels.items():
                if curr.lower().startswith(k_prefix + ":") or curr.lower().startswith(k_prefix + " "):
                    val = curr[len(k_prefix):].lstrip(": ")
                    merged_lines.append(f"{k_name}: {val}")
                    matched_prefix = True
                    break
            
            if not matched_prefix:
                merged_lines.append(curr)
            i += 1
            
        return "\n".join(merged_lines)
    except Exception as e:
        logger.warning(f"RapidOCR extraction failed: {e}")
        return ""

def ingest_image(file_path: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Ingests image (.png, .jpg) extracting dense visual descriptions, text, and data using OCR + Groq Vision."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found at {file_path}")

    sid = source_id or path.stem
    
    # Extract image attributes
    with Image.open(str(path)) as img:
        width, height = img.size
        img_format = img.format or path.suffix.replace(".", "").upper()
        img_info = dict(img.info)

    # 1. Local OCR extraction (extracts on-screen words, numbers, tables, diagrams)
    ocr_text = extract_ocr_from_image_or_array(str(path))

    # 2. Groq Vision description if configured
    vision_description = ""
    if groq_wrapper.is_configured:
        try:
            with open(str(path), "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            mime_type = f"image/{img_format.lower()}" if img_format.lower() in ["png", "jpeg", "jpg", "webp"] else "image/jpeg"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image thoroughly. Extract all visible text, numbers, dates, charts, diagram relationships, and describe key visual elements concisely for knowledge retrieval."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded_string}"
                            }
                        }
                    ]
                }
            ]
            vision_description = groq_wrapper.chat_completion(messages, model=settings.groq_vision_model)
        except Exception as e:
            logger.warning(f"Groq Vision extraction failed: {e}")

    # Check companion OCR/description txt file or PNG info
    companion_text = ""
    companion_txt = path.with_suffix(".txt")
    if companion_txt.exists():
        try:
            with open(companion_txt, "r", encoding="utf-8") as f:
                companion_text = f.read().strip()
        except Exception:
            pass
    elif "description" in img_info:
        companion_text = str(img_info["description"]).strip()

    # Synthesize rich content
    content_parts = []
    if vision_description.strip():
        content_parts.append(f"Visual Scene & Diagram Analysis:\n{vision_description.strip()}")
    if ocr_text.strip():
        content_parts.append(f"Extracted Text & Data from Image:\n{ocr_text.strip()}")
    if companion_text.strip():
        content_parts.append(f"Annotated Notes:\n{companion_text.strip()}")

    if not content_parts:
        content_parts.append(f"Visual representation: {path.stem} chart/diagram ({img_format}, {width}x{height}px) titled '{path.name}'.")

    full_description = "\n\n".join(content_parts)

    chunks: List[Dict[str, Any]] = []
    if len(full_description) > 512:
        text_slices = chunk_text(full_description, chunk_size=512, overlap=64)
        for idx, ts in enumerate(text_slices):
            chunks.append({
                "chunk_id": f"{sid}_img_{idx}",
                "source_id": sid,
                "modality": "image",
                "content": ts["content"],
                "metadata": {
                    "source_id": sid,
                    "modality": "image",
                    "width": width,
                    "height": height,
                    "file_name": path.name,
                    "has_ocr": bool(ocr_text)
                }
            })
    else:
        chunks.append({
            "chunk_id": f"{sid}_img_0",
            "source_id": sid,
            "modality": "image",
            "content": full_description.strip(),
            "metadata": {
                "source_id": sid,
                "modality": "image",
                "width": width,
                "height": height,
                "file_name": path.name,
                "has_ocr": bool(ocr_text)
            }
        })

    logger.info(f"Ingested image {path.name}: produced {len(chunks)} visual/textual chunks (OCR characters: {len(ocr_text)}).")
    return chunks

def ingest_video(file_path: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Ingests video (.mp4, .mov, .avi, .mkv, .webm) extracting audio speech, sampled visual keyframes, and on-screen OCR text."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found at {file_path}")

    sid = source_id or path.stem
    chunks: List[Dict[str, Any]] = []

    # 1. Attempt Audio extraction via ffmpeg
    temp_wav = path.with_suffix(".temp_audio.wav")
    try:
        import subprocess
        # Extract audio stream to 16kHz mono WAV
        cmd = [
            "ffmpeg", "-y", "-i", str(path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(temp_wav)
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if proc.returncode == 0 and temp_wav.exists() and temp_wav.stat().st_size > 1000:
            audio_chunks = ingest_audio(str(temp_wav), source_id=sid)
            for ac in audio_chunks:
                ac["modality"] = "video"
                ac["metadata"]["modality"] = "video"
                ac["metadata"]["track"] = "audio_speech"
                ac["metadata"]["file_name"] = path.name
                start_t = ac.get("start_time", 0.0)
                end_t = ac.get("end_time", 0.0)
                ac["content"] = f"Spoken Dialogue [{start_t:.1f}s - {end_t:.1f}s]: {ac.get('content', '')}"
                chunks.append(ac)
            logger.info(f"Extracted {len(audio_chunks)} speech chunks from video audio track.")
    except Exception as e:
        logger.warning(f"Video audio track extraction skipped or failed: {e}")
    finally:
        if temp_wav.exists():
            try:
                temp_wav.unlink()
            except Exception:
                pass

    # 2. Keyframe sampling + OCR + Vision
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        duration = total_frames / fps if fps > 0 else 0.0

        # Sample up to 5 keyframe intervals
        num_samples = min(5, max(1, int(duration // 2) or 1))
        sample_frame_indices = [int(i * total_frames / num_samples) for i in range(num_samples)]

        for idx, f_idx in enumerate(sample_frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            timestamp = round(f_idx / fps, 1) if fps > 0 else 0.0
            h, w, _ = frame.shape

            # OCR on keyframe
            ocr_text = extract_ocr_from_image_or_array(frame)

            vision_desc = ""
            if groq_wrapper.is_configured:
                try:
                    _, buffer = cv2.imencode('.jpg', frame)
                    encoded = base64.b64encode(buffer).decode('utf-8')
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Analyze this video frame at timestamp {timestamp}s. Describe visible entities, actions, text, and scene context for knowledge retrieval."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
                            ]
                        }
                    ]
                    vision_desc = groq_wrapper.chat_completion(messages, model=settings.groq_vision_model)
                except Exception as e:
                    logger.warning(f"Video frame vision inference failed: {e}")

            # Assemble frame description
            frame_parts = []
            if vision_desc.strip():
                frame_parts.append(f"Visual Scene: {vision_desc.strip()}")
            if ocr_text.strip():
                frame_parts.append(f"On-Screen Text / Slide Content:\n{ocr_text.strip()}")
            if not frame_parts:
                frame_parts.append(f"Video scene segment at {timestamp}s from '{path.name}' ({w}x{h}px).")

            combined_frame_content = f"Video Frame [{timestamp}s]:\n" + "\n".join(frame_parts)

            chunk_id = f"{sid}_vid_f{idx}"
            chunks.append({
                "chunk_id": chunk_id,
                "source_id": sid,
                "modality": "video",
                "content": combined_frame_content.strip(),
                "timestamp": timestamp,
                "start_time": timestamp,
                "end_time": round(timestamp + 2.0, 1),
                "metadata": {
                    "source_id": sid,
                    "modality": "video",
                    "timestamp": timestamp,
                    "duration": round(duration, 2),
                    "frame_index": f_idx,
                    "resolution": f"{w}x{h}",
                    "file_name": path.name,
                    "has_ocr": bool(ocr_text)
                }
            })
        cap.release()
    except Exception as e:
        logger.error(f"Error processing video frames: {e}", exc_info=True)

    if not chunks:
        chunks.append({
            "chunk_id": f"{sid}_vid_0",
            "source_id": sid,
            "modality": "video",
            "content": f"Video media recording '{path.name}' (Source ID: {sid}).",
            "timestamp": 0.0,
            "metadata": {
                "source_id": sid,
                "modality": "video",
                "file_name": path.name
            }
        })

    logger.info(f"Ingested video {path.name}: produced {len(chunks)} multimodal chunks.")
    return chunks

def ingest_file(file_path: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Universal dispatcher for multimodal ingestion based on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext in [".pdf", ".txt", ".md", ".json"]:
        return ingest_document(file_path, source_id=source_id)
    elif ext in [".mp3", ".wav", ".m4a", ".ogg"]:
        return ingest_audio(file_path, source_id=source_id)
    elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
        return ingest_image(file_path, source_id=source_id)
    elif ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        return ingest_video(file_path, source_id=source_id)
    else:
        # Default to text document ingestion
        return ingest_document(file_path, source_id=source_id)
