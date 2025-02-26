import os
import sys

from facefusion.typing import AppContext


def detect_app_context() -> AppContext:
    frame = sys._getframe(1)

    while frame:
        if os.path.join('facefusion', 'jobs') in frame.f_code.co_filename:
            return 'cli'
        if os.path.join('facefusion', 'uis') in frame.f_code.co_filename:
            return 'ui'
        if os.path.join('facefusion', 'api') in frame.f_code.co_filename:  # Добавляем проверку API контекста
            return 'api'
        frame = frame.f_back
    return 'cli'
