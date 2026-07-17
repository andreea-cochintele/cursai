"""
Conversation memory management.

This module is responsible for storing and retrieving
messages exchanged between the user and the AI assistant.
"""
from config import INPUT_TOKEN_PRICE_PER_MILLION, OUTPUT_TOKEN_PRICE_PER_MILLION,MAX_HISTORY_MESSAGES
import json
import os
from utils import count_tokens


class ConversationContext:
    """
    Manages the conversation history, dynamically builds the system
    and keeps track of cumulative token consumption across the session.
    """


    def __init__(self):
        # Global token counters
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Construct the inistial dynamic system prompt - Identity + Always-loaded procedures and facts
        system_message = self.assemble_system_prompt()

        # Calculate tokens for the initial system message and update global counters
        sys_input = count_tokens(system_message["content"])
        system_message["input_tokens"] = sys_input
        system_message["output_tokens"] = 0


        self.total_input_tokens += sys_input
        self.messages = [system_message]


    def assemble_system_prompt(self):
        """
        Loads the core identity file and appends any documents from
        the registry that have always_load
        """

        # Load the primary identity file
        try:
            with open(
                "knowledge/prompts/identity.md", "r", encoding="utf-8"
            ) as f:
                prompt_content = f.read()
        except FileNotFoundError:
            print("[ERROR]:'identity.md' is missing.")
            return []
    

        # Dynamically append essential company facts
        try: 
            company_facts = json.load(open("knowledge/facts/registry.json", "r", encoding="utf-8"))
            for document in company_facts:
                if document["always_load"]:
                    with open(f"knowledge/facts/{document['id']}.md", "r", encoding="utf-8") as f:
                        facts_content = f.read()
                        prompt_content += f"\n\n#{document['name']}\n"
                        prompt_content += "\n\n" + facts_content
        except FileNotFoundError:
            print("[Warning] 'registry.json' not found. Starting with baseline identity only.")
            company_facts = []
        except json.JSONDecodeError:
            print("[Error] 'registry.json' is corrupted. Please check its JSON syntax.")
            company_facts = []

        # Dinamically append essential procedures
        try:
            procedures = json.load(open("knowledge/procedures/registry.json", "r", encoding="utf-8"))
            for document in procedures:
                if document["always_load"]:
                    with open(f"knowledge/procedures/{document['id']}.md", "r", encoding="utf-8") as f:
                        procedures_content = f.read()
                        prompt_content += f"\n\n#{document['name']}\n"
                        prompt_content += "\n\n" + procedures_content
        except FileNotFoundError:
            print("[Warning] 'registry.json' not found. Starting with baseline identity only.")
            company_facts = []
        except json.JSONDecodeError:
            print("[Error] 'registry.json' is corrupted. Please check its JSON syntax.")
            company_facts = []

        return {
            "role": "system",
            "content": prompt_content
        }
    

    def add_message(self, message:dict, input_tokens:int = 0,output_tokens:int=0):
        """
        Adds a new message to the history and automatically recycles the context
        if the conversation grows too long, preserving the core system identity.
        """
        # Default fallback to ensure msg_to_store is defined
        msg_to_store = message.copy()

        if input_tokens or output_tokens:
            
            # Assign token values
            msg_to_store["input_tokens"] = msg_to_store.get("input_tokens",input_tokens)
            msg_to_store["output_tokens"] = msg_to_store.get("output_tokens",output_tokens)

            # Increment overall session counters
            self.total_input_tokens += msg_to_store["input_tokens"]
            self.total_output_tokens += msg_to_store["output_tokens"]
        
        # append the message with token metadata ti you message list
        self.messages.append(msg_to_store)

        # Prevent LLM context window overflow error during long chat
        if len(self.messages) > MAX_HISTORY_MESSAGES:
            print(f"\n [Context Recycling] Context reached {len(self.messages)} messages. Recycling oldest...")
            
            # Safeguard index 0: Ensure the System Identity Prompt is never purged
            system_prompt = self.messages[0]

            # Keep only the most recent interactive turns(last 10 messages)ontext Recycling] Context successfully re
            recent_messages = self.messages[-10:]

            # Reconstruct the fresh array for both lists
            self.messages = [system_prompt] + recent_messages

            print(f"[Context Recycling] Context succesfully recycled.")

    def get_history(self):
        """
        Return the chronological list of messages.
        """
        return self.messages
    
    def get_total_tokens_consumed(self):
        """
        Return the total token stats
        """

        price_per_token_in = INPUT_TOKEN_PRICE_PER_MILLION/1_000_000
        price_per_token_out = OUTPUT_TOKEN_PRICE_PER_MILLION/1_000_000

        cost = (self.total_input_tokens*price_per_token_in) + (self.total_output_tokens*price_per_token_out)
        return {
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "grand_total": self.total_input_tokens + self.total_output_tokens,
            "total_cost": f"${cost:.6f}" # 6 decimals
        }
    