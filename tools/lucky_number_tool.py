"""
Lucky Number Tool Module.

This tool calculates a dynamic "lucky number" for the user by summing the digits
of their birth date combined with the current system date.
"""

from datetime import datetime
from .tool import Tool


def lucky_number(birth_date, **kwargs):
    """
    Calculates a single integer lucky number based on the user's birth date 
    and the current system date.
    
    Args:
        birth_date (str): User's birth date (e.g., "31121993" or "31-12-1993").
        
    Returns:
        int: The calculated lucky number (sum of all digits).
    """
    if birth_date is None:
        birth_date = kwargs.get("birth_date")
        
    if not birth_date:
        return " I could not identify birth date. Try again."
    # Get the current date string in DDMMYYYY format
    current_date = datetime.now()
    current_date_str = current_date.strftime("%d%m%Y")

    # Remove any non-digit characters from birth_date to ensure clean input
    clean_birth_date = ''.join(filter(str.isdigit, str(birth_date)))

    all_digits = current_date_str + clean_birth_date

    cal_lucky_number = sum(int(digit) for digit in all_digits)
    return cal_lucky_number
    

# Define the Tool instance that will be exposed to the LLM agent
lucky_number_tool = Tool(
    name="lucky_number",
    description="Generates a lucky number based on the user's birth date and today's date",
    parameters={
        "type": "object",
        "properties": {
            "birth_date": {
                "type": "string",
                "description": "The user's birth date in format DDMMYYYY, e.g. 31121993 for 31/12/1993"
            }
        },
        "required": ["birth_date"]
    },
    callback=lucky_number
)