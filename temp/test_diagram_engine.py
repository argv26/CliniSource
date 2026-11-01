import sys
import os
sys.path.insert(0, os.path.abspath("."))

from retrieval.parallel import _execute_parallel_retrieval

queries_to_test = [
    "legal definition of tort and contract law liability",
    "treatment of alcohol associated hepatitis",
    "contraindications of OCP"
]

for q in queries_to_test:
    res = _execute_parallel_retrieval(q)
    print(f"Query: '{q}' -> Figures: {len(res['figures'])}")
    for f in res['figures']:
        print(f"   Fig chunk: {f['chunk_id']} (Page {f['page_start']})")
