import requests
import json

from config import EMBEDDINGS_MODEL, EMBEDDINGS_ENDPOINT, MIN_SIMILARITY



class EmbeddingsClient:
    """
    Handles communication with the external Embeddings API, perform cosine similarity,
    and executes semantic search over local vector databases
    """

    def get_embedding(self, text: str) -> list[float]:
        """
        Send a POST request to the configured API endpoint to retrieve vectir embeddings for a text
        """
        response = requests.post(
            EMBEDDINGS_ENDPOINT,
            json={
                "model": EMBEDDINGS_MODEL,
                "input": text
            }
        )

        if not response.ok:
            print("[ERROR]API STATUS CODE:", response.status_code)
            print("[ERROR]RESPONSE BODY:", response.text)

        response.raise_for_status()
        return response.json()["embeddings"][0]

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Computes the cosine similarity between two embedding vectors.

        Returns a float in the range [-1, 1]:
        1.0 - vectors are semantically identical
        0.0 - vectors are unrelated
        -1.0 - vectors are semantically opposite

        General interpretation:
        > 0.9      very similar
        0.7 - 0.9  similar
        0.5 - 0.7  somewhat related
        < 0.5      likely unrelated

        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a ** 2 for a in vec1) ** 0.5
        magnitude2 = sum(b ** 2 for b in vec2) ** 0.5

        # Verify if the division could give error to prevent it
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)
    

    def semantic_search(self, user_question: str, top_k: int = 2):
        """
        Performs vector search. Convert user query to embedding,
        compares it against locally stored chunks, and returns matches exceeding 
        MIN_SIMILARITY, sorted by relevance.
        """
        try:
            with open("embeddings.json", "r", encoding="utf-8") as f:
                embeddings_data = json.load(f)  # Now we have a list of dictionaries in Python
        except FileNotFoundError:
            print("[ERROR]:'embeddings.json' is missing.")
            return []

        
        # Generate the vector representation for the user's query
        question_embedding = self.get_embedding(user_question)
        results = []
        
        # Calculate similarity
        for chunk in embeddings_data:
            similarity = self.cosine_similarity(
                question_embedding,
                chunk["embedding"]
            )

            results.append({
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "similarity": similarity,
                "content": chunk["content"]
            })
            
        # Sort result descending (reverse=True)
        sorted_results = sorted(results, key=lambda x: x["similarity"], reverse=True) 

        # Filter out results that do not meet the minimum confidence
        approved_results = []
        for chunk in sorted_results:
            if chunk["similarity"] >= MIN_SIMILARITY:
                approved_results.append(chunk)

        return approved_results[:top_k]
