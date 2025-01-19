from flask import Flask, request, send_file, jsonify
import os
from typing import Optional
import uuid
import tempfile
from werkzeug.utils import secure_filename

# FaceFusion imports
from facefusion import state_manager, logger, wording, process_manager
from facefusion.jobs import job_helper, job_manager, job_runner
from facefusion.typing import Args
from facefusion.core import process_step

app = Flask(__name__)

# Создаем временные директории для файлов
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), 'facefusion_uploads')
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), 'facefusion_outputs')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_uploaded_file(file, directory: str) -> Optional[str]:
	"""Сохраняет загруженный файл и возвращает путь к нему"""
	if file:
		filename = secure_filename(str(uuid.uuid4()) + os.path.splitext(file.filename)[1])
		filepath = os.path.join(directory, filename)
		file.save(filepath)
		return filepath
	return None


def cleanup_files(*files):
	"""Удаляет временные файлы"""
	for file_path in files:
		try:
			if file_path and os.path.exists(file_path):
				os.remove(file_path)
		except Exception as e:
			logger.error(f"Error cleaning up file {file_path}: {str(e)}", __name__)


@app.route('/process', methods=['POST'])
def process():
	"""
	Основной endpoint для обработки изображений
	"""
	source_path = None
	target_path = None

	try:
		logger.info("=== Starting new request processing ===", __name__)

		# Инициализируем команду
		state_manager.init_item('command', 'api-run')
		logger.info("Command initialized", __name__)

		logger.info("Checking files in request...", __name__)
		if 'source' not in request.files or 'target' not in request.files:
			logger.error("Missing required files in request", __name__)
			return jsonify({
				'error': 'Missing required files',
				'message': 'Both source and target files are required'
			}), 400

		source_file = request.files['source']
		target_file = request.files['target']
		logger.info(f"Files received: source={source_file.filename}, target={target_file.filename}", __name__)

		# Сохраняем загруженные файлы
		source_path = save_uploaded_file(source_file, UPLOAD_DIR)
		target_path = save_uploaded_file(target_file, UPLOAD_DIR)
		logger.info(f"Files saved to: source={source_path}, target={target_path}", __name__)

		if not source_path or not target_path:
			logger.error("Failed to save uploaded files", __name__)
			return jsonify({
				'error': 'File saving failed',
				'message': 'Failed to save uploaded files'
			}), 500

		output_filename = f"output_{os.path.basename(target_path)}"
		output_path = os.path.join(OUTPUT_DIR, output_filename)
		logger.info(f"Output path will be: {output_path}", __name__)

		# Логируем перед инициализацией параметров
		logger.info("Initializing default parameters...", __name__)
		default_params = {
			'source_paths': [source_path],
			'target_path': target_path,
			'output_path': output_path,
			'face_selector_mode': 'reference',
			'reference_face_position': 0,
			'reference_face_distance': 0.6,
			'reference_frame_number': 0,
			'face_detector_model': 'yoloface',
			'face_detector_size': '640x640',  # Исправляем формат
			'face_detector_score': 0.5,
			'face_detector_angles': [0],
			'face_landmarker_model': '2dfan4',
			'face_landmarker_score': 0.5,
			'face_mask_blur': 0.3,
			'face_mask_padding': [0, 0, 0, 0],
			'face_selector_order': 'large-small',
			'temp_frame_format': 'png',
			'output_image_quality': 80,
			'execution_providers': ['cpu'],
			'execution_thread_count': 4,
			'execution_queue_count': 1,
			'processors': ['face_swapper'],
			'face_recognizer_model': 'arcface_inswapper',
			'ui_layouts': ['default'],
			'skip_audio': False,
			'output_video_encoder': 'libx264',
			'output_video_quality': 80,
			'face_mask_types': ['box'],
			'face_mask_regions': ['skin', 'left-eyebrow', 'right-eyebrow', 'left-eye', 'right-eye', 'nose', 'mouth',
								  'upper-lip', 'lower-lip'],
			'face_swapper_model': 'inswapper_128',
			'face_swapper_pixel_boost': '256x256',
			'face_enhancer_model': 'gfpgan_1.4',
			'frame_enhancer_model': 'real_esrgan_4x',
			'temp_frame_quality': 100,
			'output_video_preset': 'veryfast',
			'execution_provider_count': 1,
			'face_recognizer_score': 0.9,
			'face_analyser_direction': 'left-right',
			'face_analyser_age': None,
			'face_analyser_gender': None,
			'keep_fps': True,
			'keep_temp': False
		}

		# Явно инициализируем все параметры в state_manager
		logger.info("Setting up state manager...", __name__)
		for key, value in default_params.items():
			state_manager.init_item(key, value)
			logger.info(f"State manager: initialized {key} = {value}", __name__)

		# Важно: убедимся, что processors установлены
		processors = state_manager.get_item('processors')
		logger.info(f"Checking processors: {processors}", __name__)
		if processors is None:
			logger.error("Processors not initialized in state manager!", __name__)
			state_manager.init_item('processors', ['face_swapper'])

		# Инициализируем state manager
		for key, value in default_params.items():
			try:
				state_manager.init_item(key, value)
				logger.debug(f"Parameter initialized: {key} = {value}", __name__)
			except Exception as e:
				logger.error(f"Failed to initialize parameter {key}: {str(e)}", __name__)
				raise

		# Создаем job
		logger.info("Creating job...", __name__)
		job_id = job_helper.suggest_job_id('api')
		logger.info(f"Job ID created: {job_id}", __name__)

		# Готовим аргументы для шага
		logger.info("Preparing step arguments...", __name__)
		step_args = default_params.copy()

		# Проверяем дополнительные параметры
		if 'params' in request.form:
			logger.info("Processing additional parameters from request...", __name__)
			try:
				params = request.form.get('params', '{}')
				logger.info(f"Raw params received: {params}", __name__)
				if isinstance(params, str):
					import json
					params = json.loads(params)
				step_args.update(params)
				for key, value in params.items():
					state_manager.init_item(key, value)
					logger.info(f"Additional parameter set: {key} = {value}", __name__)
			except Exception as e:
				logger.error(f"Failed to process additional parameters: {str(e)}", __name__)

		# Запускаем обработку
		logger.info("Starting job processing...", __name__)

		logger.info("Creating job in manager...", __name__)
		if not job_manager.create_job(job_id):
			raise Exception("Failed to create job")

		logger.info("Adding step to job...", __name__)
		if not job_manager.add_step(job_id, step_args):
			raise Exception("Failed to add step to job")

		logger.info("Submitting job...", __name__)
		if not job_manager.submit_job(job_id):
			raise Exception("Failed to submit job")

		logger.info("Running job...", __name__)
		if not job_runner.run_job(job_id, process_step):
			raise Exception("Failed to run job")

		logger.info("Job processing completed, checking result...", __name__)
		if not os.path.exists(output_path):
			logger.error(f"Output file not found at: {output_path}", __name__)
			return jsonify({
				'error': 'Output not found',
				'message': 'Processing completed but output file not found'
			}), 500

		logger.info("Sending result file...", __name__)
		return send_file(output_path, as_attachment=True)

	except Exception as e:
		logger.error(f"Processing error fff: {str(e)}", __name__)
		# Добавляем вывод полного стектрейса
		import traceback
		logger.error(f"Full error traceback: {traceback.format_exc()}", __name__)
		return jsonify({
			'error': 'Processing error fff',
			'message': str(e)
		}), 500

	finally:
		cleanup_files(source_path, target_path)


@app.route('/health', methods=['GET'])
def health_check():
	"""
	Endpoint для проверки состояния сервиса
	"""
	return jsonify({
		'status': 'healthy',
		'upload_dir': os.path.exists(UPLOAD_DIR),
		'output_dir': os.path.exists(OUTPUT_DIR)
	})


def run_api(host: str = '0.0.0.0', port: int = 5000):
	"""Запускает Flask API сервер"""
	logger.info(f"Starting FaceFusion API server on {host}:{port}", __name__)
	app.run(host=host, port=port)
