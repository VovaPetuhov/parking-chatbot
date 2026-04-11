import logging
import time
from dataclasses import asdict, dataclass
from typing import Dict, List

from core.rag import get_rag_system
from core.vector_store import get_vectorstore

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    query: str
    response_time: float  # in seconds
    num_retrieved_docs: int
    response_length: int
    retrieval_successful: bool
    generation_successful: bool
    
    def to_dict(self) -> dict:
        return asdict(self)


class RAGEvaluator:
    
    def __init__(self):
        self.rag_system = get_rag_system()
        self.vectorstore_manager = get_vectorstore(read_only=True)
    
    def evaluate_query(self, query: str) -> EvaluationMetrics:
        logger.info(f"Evaluating query: {query}")
        start_time = time.time()
        
        # Retrieve documents
        try:
            docs = self.rag_system.retrieve_context(query)
            num_docs = len(docs)
            retrieval_successful = True
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            docs = []
            num_docs = 0
            retrieval_successful = False
        
        # Generate response
        try:
            response = self.rag_system.generate_answer(query)
            response_length = len(response)
            generation_successful = True
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            response = ""
            response_length = 0
            generation_successful = False
        
        end_time = time.time()
        response_time = end_time - start_time
        
        metrics = EvaluationMetrics(
            query=query,
            response_time=response_time,
            num_retrieved_docs=num_docs,
            response_length=response_length,
            retrieval_successful=retrieval_successful,
            generation_successful=generation_successful
        )
        
        logger.info(f"Evaluation complete: {response_time:.2f}s")
        return metrics
    
    def evaluate_batch(self, queries: List[str]) -> List[EvaluationMetrics]:
        results = []
        
        for i, query in enumerate(queries, 1):
            logger.info(f"Evaluating query {i}/{len(queries)}")
            metrics = self.evaluate_query(query)
            results.append(metrics)
        
        return results
    
    def generate_report(self, results: List[EvaluationMetrics]) -> Dict:
        if not results:
            return {"error": "No results to report"}
        
        total_queries = len(results)
        successful_retrievals = sum(1 for r in results if r.retrieval_successful)
        successful_generations = sum(1 for r in results if r.generation_successful)
        
        avg_response_time = sum(r.response_time for r in results) / total_queries
        avg_docs_retrieved = sum(r.num_retrieved_docs for r in results) / total_queries
        avg_response_length = sum(r.response_length for r in results) / total_queries
        
        report = {
            "total_queries": total_queries,
            "successful_retrievals": successful_retrievals,
            "successful_generations": successful_generations,
            "retrieval_success_rate": successful_retrievals / total_queries,
            "generation_success_rate": successful_generations / total_queries,
            "avg_response_time_seconds": round(avg_response_time, 3),
            "avg_docs_retrieved": round(avg_docs_retrieved, 2),
            "avg_response_length": round(avg_response_length, 2),
            "min_response_time": round(min(r.response_time for r in results), 3),
            "max_response_time": round(max(r.response_time for r in results), 3),
        }
        
        return report


def run_evaluation():
    print("RAG System Evaluation")
    # Test queries
    test_queries = [
        "What are the working hours?",
        "How much does parking cost?",
        "Do you have electric vehicle charging?",
        "What is the parking capacity?",
        "Can I reserve a parking spot in advance?",
        "What payment methods do you accept?",
        "Is the parking facility accessible for disabled persons?",
        "What are your security measures?",
    ]
    
    evaluator = RAGEvaluator()
    print(f"Running evaluation with {len(test_queries)} test queries...\n")
    results = evaluator.evaluate_batch(test_queries)
    report = evaluator.generate_report(results)
    print("\n" + "=" * 70)
    print("  Evaluation Report")
    print("=" * 70 + "\n")
    
    for key, value in report.items():
        formatted_key = key.replace("_", " ").title()
        print(f"  {formatted_key}: {value}")    
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_evaluation()
