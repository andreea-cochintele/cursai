"""Core agent orchestration.
The agent coordinates communication between
the conversation context and the language model."""
import json
from embeddings_client import EmbeddingsClient
from utils import count_tokens

class Agent:

    """
    Main Agent controller, using the RAG retrieval pipeline
    executing  LLM completions, managing tools, and logging sessions cost
    
    """
    def __init__(self, llm_client, context, tools=None):
        self.llm_client = llm_client
        self.context = context
        # Convert the tools list into a lookup dictionary mapped by tool name
        self.tools = {tool.name: tool for tool in tools} if tools else {}

    def _handle_tool_calls(self, tool_calls) -> list[dict]:
        """
        Iterate through requested tool calls, executes the matching local callbacks,
        and formats the results for LLM consuption.
        """
        results = []
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            arguments_str = tc["function"]["arguments"]
            tool_id = tc["id"]

            try:
                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                if not isinstance(arguments,dict):
                    arguments = {}
            except Exception as e:
                print(f"[ERROR] Failed to parse tool arguments: {e}")
                arguments = {}

            tool = self.tools.get(tool_name)
            if tool:
                result = tool.callback(**arguments)
            else:
                result = f"Tool '{tool_name}' not found"

            # Format the output mathing the OpenAi tool message schema
            results.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": str(result)
            })
        return results

    def _get_retrieved_context(self, user_message: str) -> str:
        """
        Queries the vector database and aggregate matching documents
        If no relevant chunks are found, returns a safe fallback instruction.
        """
        try:
            client = EmbeddingsClient()
            # Search for the best 2 fragments
            results = client.semantic_search(user_message, top_k = 2)
        except Exception as e:
            # The data base is not accesible
            print(f"[WARNING] Semantic search failed: {e}")
            return(
                "# Retrieved Context\n"
                "Warning: Internal knowledge base is currently offline.\n"
                "Fallback to you general system administration knowledge.\n"
            )
        # The search was fine but no entries over MIN_SIMILARITY
        if not results:
            return (
                "# Retrieved Context\n"
                "No specific internal documentation matches this query.\n"
                "Fallback to you general system administration knowledge\n"
            )
        # We found relevant data
        retrieved_context = "# Retrieved Context \n"
        for result in results:
            retrieved_context += result["content"] + "\n\n"
        return retrieved_context

    def _track_llm_usage(self, response) -> tuple[int, int]:
        """
        Extracts prompt and completion tokens safely from LLM response
        """
        prompt = 0
        completion = 0
        
        if isinstance(response, dict) and "usage" in response and response["usage"]:
            prompt = response["usage"].get("prompt_tokens", 0)
            completion = response["usage"].get("completion_tokens", 0)
            
        return prompt, completion

    def _execute_tool_workflow(self, initial_message) -> tuple[dict, int, int]:
        """
        Executes requested tool calls, appends results to history, and prompts the LLM again
        """
        total_prompt = 0
        total_completion = 0
        
        # Create a deep copy of the initial message to prevent mutating the original data structure
        import copy
        saved_message = copy.deepcopy(initial_message)
        
        # Ensure that function arguments are serialized back to a JSON string 
        # to satisfy the strict schema validation of the OpenAI API
        for tc in saved_message.get("tool_calls", []):
            if not isinstance(tc["function"]["arguments"], str):
                tc["function"]["arguments"] = json.dumps(tc["function"]["arguments"])

        # We add the agent's initial intent to run the tools in context
        self.context.add_message(saved_message)

        # Execute tools and append their response to history
        tool_results = self._handle_tool_calls(initial_message["tool_calls"])
        for result in tool_results:
            self.context.add_message(result)
        
        # Second run of the LLM with the tools information
        second_response = self.llm_client.generate_response(
            self.context.get_history()
        )
        
        # Capture the usage for the second LLM turn
        p, c = self._track_llm_usage(second_response)
        total_prompt += p
        total_completion += c
        
        return second_response["message"], total_prompt, total_completion

    def process_message(self, user_message: str) -> str:
        """
        The entry point for processiong incoming user prompts.
        Coordonate RAG injection, usage tracking, tool routing, and final output
        """
        # Log user's prompt
        self.context.add_message({"role": "user", "content": user_message})

        # Retrieve semantic context(RAG) and log it as a system message
        context_text = self._get_retrieved_context(user_message)
        #self.context.add_message({"role": "system", "content": context_text})

        # Compute token counts for monitoring
        total_input_tokens = count_tokens(user_message) + count_tokens(context_text)

        # Create a temporary message list for API calls
        # Take the clean history and append RAG context temporarily
        api_messages = self.context.get_history().copy()
        api_messages.append({"role":"system", "content": context_text})


        # Request initial LLM completion
        response = self.llm_client.generate_response(
            self.context.get_history(),
            tools=list(self.tools.values())
        )

        # Track usage of the firs LLM generation
        p_tokens, c_tokens = self._track_llm_usage(response)
        total_prompt = p_tokens
        total_completion = c_tokens

        message = response["message"]

        # Check if the LLM wants to perform external tool activations
        if message.get("tool_calls"):
            message, tool_p, tool_c = self._execute_tool_workflow(message)
            total_prompt += tool_p
            total_completion += tool_c


        # Emergency local calculation fallback if the API did not return usage statistics
        if total_prompt == 0:
            total_prompt = total_input_tokens
            total_completion = count_tokens(message.get("content", ""))

        # Save the final assistant answer 
        self.context.add_message(
        message, 
        input_tokens=total_prompt, 
        output_tokens=total_completion
    )

        # Fetch statistics from the conversation context
        session_stats = self.context.get_total_tokens_consumed()

        # Display session usage metrics in console
        print(f" [Mesaj curent : {total_prompt} | Răspuns: {total_completion} tokeni]")
        print(f" [TOTAL CONVERSAȚIE - Input: {session_stats['total_input']} tokeni | Output: {session_stats['total_output']} tokeni | Total: {session_stats['grand_total']} tokeni | Cost: {session_stats['total_cost']}]")
        print("-" * 60)

        return message.get("content", "")
