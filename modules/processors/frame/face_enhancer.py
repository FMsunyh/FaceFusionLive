from typing import Any, List, Dict, Literal, Optional
from argparse import ArgumentParser
import cv2
import threading
import numpy
import onnxruntime
import os
import modules.globals
import modules.processors.frame.core
from modules.core import update_status
from modules.face_analyser import get_one_face
from modules.typing import Frame, Face, Matrix
from modules.utilities import conditional_download, resolve_relative_path, is_image, is_video
from typing import Any, List, Tuple, Dict

FACE_ENHANCER = None
THREAD_SEMAPHORE = threading.Semaphore()
THREAD_LOCK = threading.Lock()
NAME = 'DLC.FACE-ENHANCER'

def encode_execution_providers(execution_providers: List[str]) -> List[str]:
    return [execution_provider.replace('ExecutionProvider', '').lower() for execution_provider in execution_providers]


def decode_execution_providers(execution_providers: List[str]) -> List[str]:
    return [provider for provider, encoded_execution_provider in zip(onnxruntime.get_available_providers(), encode_execution_providers(onnxruntime.get_available_providers()))
            if any(execution_provider in encoded_execution_provider for execution_provider in execution_providers)]


def pre_check() -> bool:
    download_directory_path = resolve_relative_path('../models')
    conditional_download(download_directory_path, [ 'https://github.com/facefusion/facefusion-assets/releases/download/models/codeformer.onnx' ])
    return True

def pre_start() -> bool:
    if not is_image(modules.globals.target_path) and not is_video(modules.globals.target_path):
        update_status('Select an image or video for target path.', NAME)
        return False
    return True

def get_face_enhancer() -> Any:
    global FACE_ENHANCER

    with THREAD_LOCK:
        if FACE_ENHANCER is None:
            # model_path = resolve_relative_path('../models/codeformer.onnx')
            model_path = resolve_relative_path('../models/gpen_bfr_512.onnx')
            FACE_ENHANCER = onnxruntime.InferenceSession(model_path, providers =decode_execution_providers(['cuda']))
    return FACE_ENHANCER


def enhance_face(target_face: Face, temp_frame: Frame) -> Frame:
	frame_processor = get_face_enhancer()
	crop_frame, affine_matrix = warp_face(target_face, temp_frame)
	crop_frame = prepare_crop_frame(crop_frame)
	frame_processor_inputs = {}
	for frame_processor_input in frame_processor.get_inputs():
		if frame_processor_input.name == 'input':
			frame_processor_inputs[frame_processor_input.name] = crop_frame
		if frame_processor_input.name == 'weight':
			frame_processor_inputs[frame_processor_input.name] = numpy.array([ 1 ], dtype = numpy.double)
	with THREAD_SEMAPHORE:
		crop_frame = frame_processor.run(None, frame_processor_inputs)[0][0]
	crop_frame = normalize_crop_frame(crop_frame)
	paste_frame = paste_back(temp_frame, crop_frame, affine_matrix)
	temp_frame = blend_frame(temp_frame, paste_frame)
	return temp_frame

def warp_face(target_face : Face, temp_frame : Frame) -> Tuple[Frame, Matrix]:
	template = numpy.array(
	[
		[ 192.98138, 239.94708 ],
		[ 318.90277, 240.1936 ],
		[ 256.63416, 314.01935 ],
		[ 201.26117, 371.41043 ],
		[ 313.08905, 371.15118 ]
	])
	affine_matrix = cv2.estimateAffinePartial2D(target_face['kps'], template, method = cv2.LMEDS)[0]
	crop_frame = cv2.warpAffine(temp_frame, affine_matrix, (512, 512))
	return crop_frame, affine_matrix


def paste_back(temp_frame : Frame, crop_frame : Frame, affine_matrix : Matrix) -> Frame:
	inverse_affine_matrix = cv2.invertAffineTransform(affine_matrix)
	temp_frame_height, temp_frame_width = temp_frame.shape[0:2]
	crop_frame_height, crop_frame_width = crop_frame.shape[0:2]
	inverse_crop_frame = cv2.warpAffine(crop_frame, inverse_affine_matrix, (temp_frame_width, temp_frame_height))
	inverse_mask = numpy.ones((crop_frame_height, crop_frame_width, 3), dtype = numpy.float32)
	inverse_mask_frame = cv2.warpAffine(inverse_mask, inverse_affine_matrix, (temp_frame_width, temp_frame_height))
	inverse_mask_frame = cv2.erode(inverse_mask_frame, numpy.ones((2, 2)))
	inverse_mask_border = inverse_mask_frame * inverse_crop_frame
	inverse_mask_area = numpy.sum(inverse_mask_frame) // 3
	inverse_mask_edge = int(inverse_mask_area ** 0.5) // 20
	inverse_mask_radius = inverse_mask_edge * 2
	inverse_mask_center = cv2.erode(inverse_mask_frame, numpy.ones((inverse_mask_radius, inverse_mask_radius)))
	inverse_mask_blur_size = inverse_mask_edge * 2 + 1
	inverse_mask_blur_area = cv2.GaussianBlur(inverse_mask_center, (inverse_mask_blur_size, inverse_mask_blur_size), 0)
	temp_frame = inverse_mask_blur_area * inverse_mask_border + (1 - inverse_mask_blur_area) * temp_frame
	temp_frame = temp_frame.clip(0, 255).astype(numpy.uint8)
	return temp_frame


def prepare_crop_frame(crop_frame : Frame) -> Frame:
	crop_frame = crop_frame[:, :, ::-1] / 255.0
	crop_frame = (crop_frame - 0.5) / 0.5
	crop_frame = numpy.expand_dims(crop_frame.transpose(2, 0, 1), axis = 0).astype(numpy.float32)
	return crop_frame


def normalize_crop_frame(crop_frame : Frame) -> Frame:
	crop_frame = numpy.clip(crop_frame, -1, 1)
	crop_frame = (crop_frame + 1) / 2
	crop_frame = crop_frame.transpose(1, 2, 0)
	crop_frame = (crop_frame * 255.0).round()
	crop_frame = crop_frame.astype(numpy.uint8)[:, :, ::-1]
	return crop_frame

def blend_frame(temp_frame : Frame, paste_frame : Frame) -> Frame:
	face_enhancer_blend = 1 - (80 / 100)
	temp_frame = cv2.addWeighted(temp_frame, face_enhancer_blend, paste_frame, 1 - face_enhancer_blend, 0)
	return temp_frame

def process_frame(source_face: Face, temp_frame: Frame) -> Frame:
    target_face = get_one_face(temp_frame)
    if target_face:
        temp_frame = enhance_face(target_face, temp_frame)
    return temp_frame


def process_frames(source_path: str, temp_frame_paths: List[str], progress: Any = None) -> None:
    for temp_frame_path in temp_frame_paths:
        temp_frame = cv2.imread(temp_frame_path)
        result = process_frame(None, temp_frame)
        cv2.imwrite(temp_frame_path, result)
        if progress:
            progress.update(1)


def process_image(source_path: str, target_path: str, output_path: str) -> None:
    target_frame = cv2.imread(target_path)
    result = process_frame(None, target_frame)
    cv2.imwrite(output_path, result)


def process_video(source_path: str, temp_frame_paths: List[str]) -> None:
    modules.processors.frame.core.process_video(None, temp_frame_paths, process_frames)
