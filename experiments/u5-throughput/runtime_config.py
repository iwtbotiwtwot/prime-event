"""Runtime source identity and explicit CUDA role assignments."""
import hashlib
import re

SOURCE_FILES = (
    'accelerator.cpp', 'accelerator.cu', 'accelerated.py', 'pilot.py',
    'pipeline.py', 'native_history.cpp', 'native_history.py', 'journal.py',
    'gpu_grade.cu', 'gpu_history.cu', 'history_exports.cpp', 'gpu_roles.py',
    'runtime_config.py',
)

def add_gpu_arguments(parser):
    parser.add_argument('--proposal-gpu', type=int, default=0)
    parser.add_argument('--history-gpu', type=int, help='Use this GPU for cached actual-history marking')
    parser.add_argument('--grade-gpu', type=int, help='Use this GPU for ordered event extraction and grading')
    parser.add_argument('--gpu-cache-mib', type=int, default=16384)
    parser.add_argument('--cuda-arch', default='sm_86', help='Native CUDA target; Blackwell uses sm_120')

def gpu_options(args):
    return {name: getattr(args, name) for name in
            ('proposal_gpu', 'history_gpu', 'grade_gpu', 'gpu_cache_mib', 'cuda_arch')}

def validate_gpu_arguments(parser, args, backend='gpu', pipeline=True):
    devices = [args.proposal_gpu, args.history_gpu, args.grade_gpu]
    if any(device is not None and device < 0 for device in devices):
        parser.error('GPU device indices must be nonnegative')
    if args.gpu_cache_mib < 1 or not re.fullmatch(r'sm_[0-9]+', args.cuda_arch):
        parser.error('positive GPU cache size and a CUDA target such as sm_120 required')
    if (args.history_gpu is not None or args.grade_gpu is not None) and (backend != 'gpu' or not pipeline):
        parser.error('history/grade GPU roles require the GPU pipeline')

def accelerator_identity(code, backend, pipeline, args):
    return dict(backend=backend, pipeline=pipeline,
                files={name: hashlib.sha256((code/name).read_bytes()).hexdigest()
                       for name in SOURCE_FILES}, **gpu_options(args))
