import os
import tempfile

# Must run before `src.config.settings` is imported anywhere (it's built at
# module import time), otherwise Seq2PointNILMManager.__init__ tries to
# mkdir the production /app/models path.
os.environ.setdefault("NILM_MODEL_PATH", tempfile.mkdtemp())
