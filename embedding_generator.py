"""
Local Vector Database Generator.

This module loads the chunked documents, requests their vector embeddings 
via the Embeddings Client, and saves the serialized results to a local 
JSON database for semantic search retrieval.
"""

import json
import os

from document_chunker import DocumentChunker
from embeddings_client import EmbeddingsClient


class EmbeddingGenerator:
    """
    Manages the lifecycle of the local embeddings database.
    Prevents redundant API calls by verifying existing databases, 
    and serializes vector data with full document metadata.
    """

    def generate_embeddings(self):
        """
        Processes all knowledge base files, generates their embeddings,
        and saves them locally to 'embeddings.json'.
        """
        # Skip generation if the local vector database already exists
        if os.path.exists("embeddings.json"):
            print("[INFO] embedding.json already exists.")
            return
        
        # Load and chunk all dynamic documents
        chunker = DocumentChunker()
        chunks = chunker.load_documents()

        if not chunks:
            print("[Warning] No document chunks found. Database generation aborted." )
            return
        

        print(f"[INFO] Founf {len(chunks)} chunks. Generating embeddings...")
        client = EmbeddingsClient()
        embeddings_data = []

        # Process each chunck automatically
        for id, chunk in enumerate(chunks, 1):
            try:
                # Generate embedding vector for the current chunck content
                embedding = client.get_embedding(
                    chunk["content"]
                )
                # Append structured chunk metadata, content, token counts
                embeddings_data.append(
                    {
                        "document_id": chunk["document_id"],
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"],
                        "token_count": chunk.get("token_count",0),  #Save the token count from chunker
                        "embedding": embedding
                    }
                )
                print(f"Processed chunk {id}/{len(chunks)} (ID: {chunk['document_id']})")
            except Exception as e:
                print(f"[ERROR] Failed to generate embedding for chunk{id}/{len(chunks)} : {e} ")
        
        
        print(f"[INFO] Saving {len(embeddings_data)} vectors to 'embeddings.json'...")
        try:
            with open("embeddings.json","w",encoding="utf-8") as f:
                json.dump(
                    embeddings_data,
                    f,
                    ensure_ascii=False,
                    indent=4
                )
        except FileNotFoundError:
            print("[ERROR]:'embeddings.json' is missing.")
            return []
        print("[SUCCES] Vector databse initializes and saved succesfully")
        