import sys
import traceback

sys.path.append('.')
from backend import get_under_review_documents

try:
    print(get_under_review_documents())
except Exception as e:
    traceback.print_exc()
