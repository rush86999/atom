"""
ATOM Vision AI Service
Advanced computer vision and image/video analysis with multi-modal integration
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import uuid
import base64
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
import io
import cv2

# Vision AI Models
try:
    import torch
    import torchvision.transforms as transforms
    from transformers import AutoProcessor, AutoModelForVision2Seq
    import clip
except ImportError:
    torch = None
    torchvision = None
    AutoProcessor = AutoModelForVision2Seq = None
    clip = None

# OpenAI Vision Models
try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None

# Google Cloud Vision
try:
    from google.cloud import vision
    from google.cloud.vision import types
except ImportError:
    vision = None
    types = None

# Existing Services
from advanced_ai_models_service import create_advanced_ai_models_service, AIModelType

class VisionTask(Enum):
    """Vision AI task types"""
    IMAGE_ANALYSIS = "image_analysis"
    OBJECT_DETECTION = "object_detection"
    FACE_RECOGNITION = "face_recognition"
    TEXT_RECOGNITION = "text_recognition"
    SCENE_UNDERSTANDING = "scene_understanding"
    VIDEO_ANALYSIS = "video_analysis"
    DOCUMENT_ANALYSIS = "document_analysis"
    CONTENT_MODERATION = "content_moderation"
    MULTIMODAL_ANALYSIS = "multimodal_analysis"

class VisionModel(Enum):
    """Supported vision AI models"""
    OPENAI_VISION = "openai_vision"
    GOOGLE_VISION = "google_vision"
    CLIP_VIT = "clip_vit"
    BLIP_2 = "blip_2"
    LLAVA = "llava"
    CUSTOM_MODEL = "custom_model"

@dataclass
class VisionRequest:
    """Vision AI request"""
    request_id: str
    task_type: VisionTask
    vision_model: VisionModel
    image_data: Union[str, bytes, np.ndarray]  # URL, base64, or image array
    image_format: Optional[str] = None
    text_prompt: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    options: Dict[str, Any] = None
    priority: int = 5
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.options is None:
            self.options = {}
        if self.context is None:
            self.context = {}

@dataclass
class DetectedObject:
    """Detected object information"""
    object_id: str
    class_name: str
    confidence: float
    bounding_box: Dict[str, float]
    attributes: Dict[str, Any]
    timestamp: datetime
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}

@dataclass
class FaceAnalysis:
    """Face analysis results"""
    face_id: str
    confidence: float
    bounding_box: Dict[str, float]
    landmarks: Dict[str, Tuple[float, float]]
    emotions: Dict[str, float]
    age_estimate: Optional[int]
    gender_estimate: Optional[str]
    embedding: Optional[List[float]]
    timestamp: datetime

@dataclass
class SceneAnalysis:
    """Scene understanding results"""
    scene_id: str
    description: str
    confidence: float
    objects: List[str]
    activities: List[str]
    context: Dict[str, Any]
    timestamp: datetime
    
    def __post_init__(self):
        if self.objects is None:
            self.objects = []
        if self.activities is None:
            self.activities = []
        if self.context is None:
            self.context = {}

@dataclass
class VisionResponse:
    """Vision AI response"""
    request_id: str
    task_type: VisionTask
    vision_model: VisionModel
    success: bool
    results: Dict[str, Any]
    processing_time: float
    cost: float
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def __post_init__(self):
        if self.results is None:
            self.results = {}
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class VisionAIService:
    """Enterprise vision AI service with multi-modal capabilities"""
    
    def __init__(self):
        # API keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.google_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        # Vision models
        self.vision_models = {}
        self.model_processors = {}
        
        # Initialize vision models
        self._initialize_vision_models()
        
        # Existing AI services
        self.advanced_ai = create_advanced_ai_models_service()
        
        # Performance tracking
        self.performance_metrics = {}
        
        logger.info("Vision AI Service initialized")
    
    def _initialize_vision_models(self):
        """Initialize vision AI models"""
        try:
            # Initialize OpenAI Vision
            if self.openai_api_key and OpenAI:
                openai_client = OpenAI(api_key=self.openai_api_key)
                self.vision_models[VisionModel.OPENAI_VISION] = openai_client
                logger.info("OpenAI Vision model initialized")
            
            # Initialize Google Vision
            if self.google_credentials and vision:
                vision_client = vision.ImageAnnotatorClient.from_service_account_json(self.google_credentials)
                self.vision_models[VisionModel.GOOGLE_VISION] = vision_client
                logger.info("Google Vision model initialized")
            
            # Initialize CLIP
            if torch and clip:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                clip_model, clip_preprocess = clip.load("ViT-B/32", device=device)
                self.vision_models[VisionModel.CLIP_VIT] = {
                    "model": clip_model,
                    "preprocess": clip_preprocess,
                    "device": device
                }
                logger.info("CLIP ViT model initialized")
            
            # Initialize BLIP-2
            if torch and AutoProcessor and AutoModelForVision2Seq:
                try:
                    processor = AutoProcessor.from_pretrained("Salesforce/blip2-opt-2.7b")
                    model = AutoModelForVision2Seq.from_pretrained("Salesforce/blip2-opt-2.7b")
                    
                    if torch.cuda.is_available():
                        model = model.cuda()
                    
                    self.vision_models[VisionModel.BLIP_2] = {
                        "processor": processor,
                        "model": model
                    }
                    logger.info("BLIP-2 model initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize BLIP-2: {e}")
            
            # Initialize LLaVA
            if torch and AutoProcessor and AutoModelForVision2Seq:
                try:
                    llava_processor = AutoProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
                    llava_model = AutoModelForVision2Seq.from_pretrained("llava-hf/llava-1.5-7b-hf")
                    
                    if torch.cuda.is_available():
                        llava_model = llava_model.cuda()
                    
                    self.vision_models[VisionModel.LLAVA] = {
                        "processor": llava_processor,
                        "model": llava_model
                    }
                    logger.info("LLaVA model initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize LLaVA: {e}")
            
            logger.info(f"Initialized {len(self.vision_models)} vision models")
            
        except Exception as e:
            logger.error(f"Failed to initialize vision models: {e}")
    
    async def process_vision_request(self, request: VisionRequest) -> VisionResponse:
        """Process vision AI request"""
        try:
            logger.info(f"Processing vision request {request.request_id} with model {request.vision_model}")
            start_time = datetime.utcnow()
            
            # Validate model availability
            if request.vision_model not in self.vision_models:
                raise ValueError(f"Vision model {request.vision_model} not available")
            
            # Prepare image data
            image_data = await self._prepare_image_data(request.image_data, request.image_format)
            
            # Route to appropriate processor
            if request.vision_model == VisionModel.OPENAI_VISION:
                results = await self._process_openai_vision(request, image_data)
            elif request.vision_model == VisionModel.GOOGLE_VISION:
                results = await self._process_google_vision(request, image_data)
            elif request.vision_model == VisionModel.CLIP_VIT:
                results = await self._process_clip_vision(request, image_data)
            elif request.vision_model == VisionModel.BLIP_2:
                results = await self._process_blip2_vision(request, image_data)
            elif request.vision_model == VisionModel.LLAVA:
                results = await self._process_llava_vision(request, image_data)
            else:
                raise ValueError(f"Unsupported vision model: {request.vision_model}")
            
            # Calculate processing time and cost
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            cost = self._calculate_vision_cost(request.vision_model, image_data)
            
            # Update performance metrics
            self._update_performance_metrics(request.vision_model, processing_time, request.success)
            
            response = VisionResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                vision_model=request.vision_model,
                success=True,
                results=results,
                processing_time=processing_time,
                cost=cost,
                metadata={"image_size": len(image_data), "model": request.vision_model.value}
            )
            
            logger.info(f"Completed vision request {request.request_id} in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Failed to process vision request {request.request_id}: {e}")
            return VisionResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                vision_model=request.vision_model,
                success=False,
                results={"error": str(e)},
                processing_time=0.0,
                cost=0.0,
                metadata={"error": True}
            )
    
    async def _prepare_image_data(self, image_data: Union[str, bytes, np.ndarray], 
                               image_format: Optional[str] = None) -> bytes:
        """Prepare image data for processing"""
        try:
            if isinstance(image_data, str):
                # Handle URL or base64
                if image_data.startswith(('http://', 'https://')):
                    # Download image from URL
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_data) as response:
                            image_bytes = await response.read()
                else:
                    # Handle base64
                    if image_data.startswith('data:image'):
                        # Remove data URL prefix
                        image_data = image_data.split(',')[1]
                    image_bytes = base64.b64decode(image_data)
            elif isinstance(image_data, np.ndarray):
                # Convert numpy array to bytes
                image = Image.fromarray(image_data)
                buffer = io.BytesIO()
                image.save(buffer, format=image_format or 'PNG')
                image_bytes = buffer.getvalue()
            else:
                # Use bytes directly
                image_bytes = image_data
            
            return image_bytes
            
        except Exception as e:
            logger.error(f"Failed to prepare image data: {e}")
            raise ValueError(f"Invalid image data: {e}")
    
    async def _process_openai_vision(self, request: VisionRequest, image_data: bytes) -> Dict[str, Any]:
        """Process image with OpenAI Vision API"""
        try:
            client = self.vision_models[VisionModel.OPENAI_VISION]
            
            # Prepare message with image
            message_content = [
                {
                    "type": "text",
                    "text": request.text_prompt or "Analyze this image in detail."
                }
            ]
            
            # Add image
            base64_image = base64.b64encode(image_data).decode('utf-8')
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
            
            # Make API call
            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": message_content
                    }
                ],
                max_tokens=request.options.get("max_tokens", 500),
                temperature=request.options.get("temperature", 0.7)
            )
            
            return {
                "analysis": response.choices[0].message.content,
                "model": "gpt-4-vision-preview",
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "confidence": 0.85  # OpenAI doesn't provide confidence
            }
            
        except Exception as e:
            logger.error(f"OpenAI Vision processing failed: {e}")
            return {"error": str(e), "provider": "openai"}
    
    async def _process_google_vision(self, request: VisionRequest, image_data: bytes) -> Dict[str, Any]:
        """Process image with Google Vision API"""
        try:
            client = self.vision_models[VisionModel.GOOGLE_VISION]
            
            # Create image object
            image = types.Image(content=image_data)
            
            results = {}
            
            # Process based on task type
            if request.task_type == VisionTask.OBJECT_DETECTION:
                response = client.object_localization(image=image)
                objects = []
                for object_annotation in response.localized_object_annotations:
                    objects.append({
                        "name": object_annotation.name,
                        "confidence": object_annotation.score,
                        "bounding_box": {
                            "normalized_vertices": [
                                {"x": vertex.x, "y": vertex.y} 
                                for vertex in object_annotation.bounding_poly.normalized_vertices
                            ]
                        }
                    })
                results["objects"] = objects
            
            elif request.task_type == VisionTask.FACE_RECOGNITION:
                response = client.face_detection(image=image)
                faces = []
                for face_annotation in response.face_annotations:
                    faces.append({
                        "confidence": face_annotation.detection_confidence,
                        "bounding_box": {
                            "vertices": [
                                {"x": vertex.x, "y": vertex.y} 
                                for vertex in face_annotation.bounding_poly.vertices
                            ]
                        },
                        "joy": face_annotation.joy_likelihood,
                        "sorrow": face_annotation.sorrow_likelihood,
                        "anger": face_annotation.anger_likelihood,
                        "surprise": face_annotation.surprise_likelihood
                    })
                results["faces"] = faces
            
            elif request.task_type == VisionTask.TEXT_RECOGNITION:
                response = client.text_detection(image=image)
                texts = []
                for text_annotation in response.text_annotations:
                    texts.append({
                        "text": text_annotation.description,
                        "confidence": text_annotation.score,
                        "bounding_box": {
                            "vertices": [
                                {"x": vertex.x, "y": vertex.y} 
                                for vertex in text_annotation.bounding_poly.vertices
                            ]
                        }
                    })
                results["texts"] = texts
            
            elif request.task_type == VisionTask.IMAGE_ANALYSIS:
                # Label detection
                response = client.label_detection(image=image)
                labels = []
                for label_annotation in response.label_annotations:
                    labels.append({
                        "label": label_annotation.description,
                        "confidence": label_annotation.score
                    })
                results["labels"] = labels
            
            elif request.task_type == VisionTask.SCENE_UNDERSTANDING:
                # Web detection for scene understanding
                response = client.web_detection(image=image)
                web_entities = []
                for web_entity in response.web_detection.web_entities:
                    web_entities.append({
                        "description": web_entity.description,
                        "score": web_entity.score
                    })
                results["web_entities"] = web_entities
            
            results["provider"] = "google_vision"
            results["model"] = "vision_api"
            
            return results
            
        except Exception as e:
            logger.error(f"Google Vision processing failed: {e}")
            return {"error": str(e), "provider": "google_vision"}
    
    async def _process_clip_vision(self, request: VisionRequest, image_data: bytes) -> Dict[str, Any]:
        """Process image with CLIP ViT"""
        try:
            clip_data = self.vision_models[VisionModel.CLIP_VIT]
            model = clip_data["model"]
            preprocess = clip_data["preprocess"]
            device = clip_data["device"]
            
            # Load and preprocess image
            image = Image.open(io.BytesIO(image_data))
            image_tensor = preprocess(image).unsqueeze(0).to(device)
            
            # Process based on task
            if request.task_type == VisionTask.MULTIMODAL_ANALYSIS and request.text_prompt:
                # Text-image similarity
                text_tokens = clip.tokenize([request.text_prompt]).to(device)
                
                with torch.no_grad():
                    image_features = model.encode_image(image_tensor)
                    text_features = model.encode_text(text_tokens)
                    
                    # Calculate similarity
                    similarity = torch.cosine_similarity(image_features, text_features, dim=1)
                
                return {
                    "similarity": similarity.item(),
                    "text": request.text_prompt,
                    "provider": "clip",
                    "model": "ViT-B/32"
                }
            else:
                # General image classification (using ImageNet classes)
                with torch.no_grad():
                    image_features = model.encode_image(image_tensor)
                
                return {
                    "image_features": image_features.cpu().numpy().tolist(),
                    "feature_dim": image_features.shape[1],
                    "provider": "clip",
                    "model": "ViT-B/32"
                }
            
        except Exception as e:
            logger.error(f"CLIP ViT processing failed: {e}")
            return {"error": str(e), "provider": "clip"}
    
    async def _process_blip2_vision(self, request: VisionRequest, image_data: bytes) -> Dict[str, Any]:
        """Process image with BLIP-2"""
        try:
            blip_data = self.vision_models[VisionModel.BLIP_2]
            processor = blip_data["processor"]
            model = blip_data["model"]
            
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Prepare inputs
            inputs = processor(image, text=request.text_prompt or "Describe this image:", return_tensors="pt")
            
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate response
            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_length=50)
                generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return {
                "description": generated_text,
                "prompt": request.text_prompt,
                "provider": "blip2",
                "model": "blip2-opt-2.7b"
            }
            
        except Exception as e:
            logger.error(f"BLIP-2 processing failed: {e}")
            return {"error": str(e), "provider": "blip2"}
    
    async def _process_llava_vision(self, request: VisionRequest, image_data: bytes) -> Dict[str, Any]:
        """Process image with LLaVA"""
        try:
            llava_data = self.vision_models[VisionModel.LLAVA]
            processor = llava_data["processor"]
            model = llava_data["model"]
            
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Prepare inputs
            prompt = request.text_prompt or "Describe this image in detail."
            inputs = processor(prompt, image, return_tensors="pt")
            
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate response
            with torch.no_grad():
                outputs = model.generate(**inputs, max_new_tokens=100)
                generated_text = processor.decode(outputs[0], skip_special_tokens=True)
            
            return {
                "description": generated_text,
                "prompt": prompt,
                "provider": "llava",
                "model": "llava-1.5-7b-hf"
            }
            
        except Exception as e:
            logger.error(f"LLaVA processing failed: {e}")
            return {"error": str(e), "provider": "llava"}
    
    async def analyze_video(self, video_data: Union[str, bytes], 
                         frame_interval: int = 30) -> List[VisionResponse]:
        """Analyze video frame by frame"""
        try:
            # Open video
            if isinstance(video_data, str):
                cap = cv2.VideoCapture(video_data)
            else:
                # Handle video bytes
                video_buffer = io.BytesIO(video_data)
                temp_file = "/tmp/temp_video.mp4"
                with open(temp_file, "wb") as f:
                    f.write(video_buffer)
                cap = cv2.VideoCapture(temp_file)
            
            frame_results = []
            frame_count = 0
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            logger.info(f"Analyzing video with {total_frames} frames at {fps} FPS")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process every nth frame
                if frame_count % frame_interval == 0:
                    # Convert frame to bytes
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = buffer.tobytes()
                    
                    # Create vision request
                    request = VisionRequest(
                        request_id=str(uuid.uuid4()),
                        task_type=VisionTask.IMAGE_ANALYSIS,
                        vision_model=VisionModel.OPENAI_VISION,  # Default to best model
                        image_data=frame_bytes,
                        image_format='JPEG',
                        options={"max_tokens": 200}  # Reduced for video processing
                    )
                    
                    # Process frame
                    result = await self.process_vision_request(request)
                    frame_results.append(result)
                    
                    logger.info(f"Processed frame {frame_count}/{total_frames}")
                
                frame_count += 1
            
            cap.release()
            logger.info(f"Video analysis complete. Processed {len(frame_results)} frames")
            
            return frame_results
            
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            return []
    
    async def detect_objects(self, image_data: Union[str, bytes], 
                          model: VisionModel = VisionModel.GOOGLE_VISION) -> List[DetectedObject]:
        """Detect objects in image"""
        try:
            request = VisionRequest(
                request_id=str(uuid.uuid4()),
                task_type=VisionTask.OBJECT_DETECTION,
                vision_model=model,
                image_data=image_data
            )
            
            response = await self.process_vision_request(request)
            
            objects = []
            if response.success and "objects" in response.results:
                for obj_data in response.results["objects"]:
                    obj = DetectedObject(
                        object_id=str(uuid.uuid4()),
                        class_name=obj_data["name"],
                        confidence=obj_data["confidence"],
                        bounding_box=obj_data["bounding_box"],
                        attributes={"provider": "google_vision"}
                    )
                    objects.append(obj)
            
            return objects
            
        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return []
    
    async def recognize_faces(self, image_data: Union[str, bytes],
                           model: VisionModel = VisionModel.GOOGLE_VISION) -> List[FaceAnalysis]:
        """Recognize faces in image"""
        try:
            request = VisionRequest(
                request_id=str(uuid.uuid4()),
                task_type=VisionTask.FACE_RECOGNITION,
                vision_model=model,
                image_data=image_data
            )
            
            response = await self.process_vision_request(request)
            
            faces = []
            if response.success and "faces" in response.results:
                for face_data in response.results["faces"]:
                    face = FaceAnalysis(
                        face_id=str(uuid.uuid4()),
                        confidence=face_data["confidence"],
                        bounding_box=face_data["bounding_box"],
                        landmarks={},
                        emotions={
                            "joy": face_data.get("joy", 0),
                            "sorrow": face_data.get("sorrow", 0),
                            "anger": face_data.get("anger", 0),
                            "surprise": face_data.get("surprise", 0)
                        },
                        age_estimate=None,
                        gender_estimate=None,
                        embedding=None,
                        timestamp=datetime.utcnow()
                    )
                    faces.append(face)
            
            return faces
            
        except Exception as e:
            logger.error(f"Face recognition failed: {e}")
            return []
    
    async def extract_text_from_image(self, image_data: Union[str, bytes],
                                   model: VisionModel = VisionModel.GOOGLE_VISION) -> List[str]:
        """Extract text from image using OCR"""
        try:
            request = VisionRequest(
                request_id=str(uuid.uuid4()),
                task_type=VisionTask.TEXT_RECOGNITION,
                vision_model=model,
                image_data=image_data
            )
            
            response = await self.process_vision_request(request)
            
            texts = []
            if response.success and "texts" in response.results:
                for text_data in response.results["texts"]:
                    texts.append(text_data["text"])
            
            return texts
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return []
    
    async def analyze_document(self, image_data: Union[str, bytes],
                            model: VisionModel = VisionModel.OPENAI_VISION) -> Dict[str, Any]:
        """Analyze document with vision AI"""
        try:
            prompt = """
            Analyze this document image and provide:
            1. Document type (invoice, receipt, contract, etc.)
            2. Key information extracted
            3. Structure and layout analysis
            4. Any important numbers, dates, or entities
            5. Overall summary
            """
            
            request = VisionRequest(
                request_id=str(uuid.uuid4()),
                task_type=VisionTask.DOCUMENT_ANALYSIS,
                vision_model=model,
                image_data=image_data,
                text_prompt=prompt,
                options={"max_tokens": 800}
            )
            
            response = await self.process_vision_request(request)
            
            if response.success:
                # Parse structured response
                return {
                    "document_analysis": response.results.get("analysis", ""),
                    "provider": "openai_vision",
                    "confidence": 0.8
                }
            else:
                return {"error": response.results.get("error", "Unknown error")}
            
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return {"error": str(e)}
    
    def _calculate_vision_cost(self, model: VisionModel, image_data: bytes) -> float:
        """Calculate processing cost for vision model"""
        try:
            # Rough cost estimation
            image_size_mb = len(image_data) / (1024 * 1024)
            
            if model == VisionModel.OPENAI_VISION:
                # OpenAI Vision costs per token
                return image_size_mb * 0.01  # Rough estimate
            elif model == VisionModel.GOOGLE_VISION:
                # Google Vision costs per image
                return 0.0015 if image_size_mb < 4 else 0.003  # $1.50 per 1000 images
            elif model in [VisionModel.CLIP_VIT, VisionModel.BLIP_2, VisionModel.LLAVA]:
                # Local models - compute cost
                return image_size_mb * 0.0001  # Rough compute cost
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Failed to calculate vision cost: {e}")
            return 0.0
    
    def _update_performance_metrics(self, model: VisionModel, processing_time: float, success: bool):
        """Update performance metrics"""
        if model not in self.performance_metrics:
            self.performance_metrics[model] = {
                "total_requests": 0,
                "successful_requests": 0,
                "total_time": 0.0,
                "average_time": 0.0,
                "success_rate": 0.0
            }
        
        metrics = self.performance_metrics[model]
        metrics["total_requests"] += 1
        metrics["total_time"] += processing_time
        
        if success:
            metrics["successful_requests"] += 1
        
        metrics["average_time"] = metrics["total_time"] / metrics["total_requests"]
        metrics["success_rate"] = metrics["successful_requests"] / metrics["total_requests"]
    
    def get_available_models(self) -> Dict[str, Any]:
        """Get available vision models and their capabilities"""
        models = {}
        
        for model in VisionModel:
            models[model.value] = {
                "available": model in self.vision_models,
                "capabilities": self._get_model_capabilities(model),
                "supported_tasks": self._get_supported_tasks(model)
            }
        
        return {
            "models": models,
            "total_models": len([m for m in VisionModel if m in self.vision_models]),
            "performance_metrics": self.performance_metrics
        }
    
    def _get_model_capabilities(self, model: VisionModel) -> List[str]:
        """Get capabilities for specific model"""
        capabilities_map = {
            VisionModel.OPENAI_VISION: ["image_analysis", "text_extraction", "document_analysis", "multimodal"],
            VisionModel.GOOGLE_VISION: ["object_detection", "face_recognition", "text_recognition", "label_detection", "web_detection"],
            VisionModel.CLIP_VIT: ["image_embedding", "text_image_similarity", "classification"],
            VisionModel.BLIP_2: ["image_description", "visual_question_answering", "multimodal"],
            VisionModel.LLAVA: ["image_description", "visual_question_answering", "multimodal", "document_analysis"]
        }
        
        return capabilities_map.get(model, [])
    
    def _get_supported_tasks(self, model: VisionModel) -> List[str]:
        """Get supported tasks for specific model"""
        task_map = {
            VisionModel.OPENAI_VISION: [VisionTask.IMAGE_ANALYSIS, VisionTask.DOCUMENT_ANALYSIS, VisionTask.MULTIMODAL_ANALYSIS],
            VisionModel.GOOGLE_VISION: [VisionTask.OBJECT_DETECTION, VisionTask.FACE_RECOGNITION, VisionTask.TEXT_RECOGNITION, VisionTask.IMAGE_ANALYSIS, VisionTask.SCENE_UNDERSTANDING],
            VisionModel.CLIP_VIT: [VisionTask.MULTIMODAL_ANALYSIS],
            VisionModel.BLIP_2: [VisionTask.IMAGE_ANALYSIS, VisionTask.MULTIMODAL_ANALYSIS],
            VisionModel.LLAVA: [VisionTask.IMAGE_ANALYSIS, VisionTask.MULTIMODAL_ANALYSIS, VisionTask.DOCUMENT_ANALYSIS]
        }
        
        return [t.value for t in task_map.get(model, [])]

# Factory function
def create_vision_ai_service() -> VisionAIService:
    """Create vision AI service instance"""
    return VisionAIService()