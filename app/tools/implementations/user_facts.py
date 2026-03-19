"""
User Facts Tools - Add, update, and delete user facts.
"""
from app.tools.base import BaseTool
from app.repositories.user_facts_repository import load_user_facts, upsert_user_fact, delete_user_fact as delete_user_fact_repo
from app.utils.helpers import find_fact_by_key
from app.auth.context import get_current_user_id, get_current_db_session
from app.types.internal.user_facts import UserFact


class AddUserFactTool(BaseTool):
    """
    Tool for adding or updating a user fact.
    """
    
    name = "add_user_fact"
    summary = "Save user's personal information (key-value). Use when user requests to remember info about them."
    category = "user_data"
    description = """Save user's personal information as key-value pair to long-term memory. Use ONLY when user explicitly requests to remember their info (keywords: "remember", "save", "store"; examples: "Remember that my name is Bao", "Save that I live in Hanoi"). NEVER auto-detect and save info from casual conversation; stores as key-value pair and returns confirmation."""
    
    def execute(self, key: str, value: str) -> str:
        """
        Add or update a user fact.
        
        Args:
            key: Fact key (e.g., "name", "company")
            value: Fact value
            
        Returns:
            Success or error message
        """
        try:
            # Get user_id and db from context
            user_id = get_current_user_id()
            db = get_current_db_session()
            if not user_id:
                return "Error: Cannot determine user_id. Please log in again."
            
            if not key or not key.strip():
                return "Error: Key cannot be empty."
            
            if not value or not value.strip():
                return "Error: Value cannot be empty."
            
            key_clean = key.strip()
            value_clean = value.strip()
            
            # Upsert fact in database
            fact: UserFact = {
                "user_id": user_id,
                "key": key_clean,
                "value": value_clean,
            }
            saved_fact = upsert_user_fact(fact, db)
            if saved_fact:
                return f"Saved: {key_clean} = {value_clean}"
            else:
                return "Error: Failed to save information."
                    
        except Exception as e:
            return f"Error adding user fact: {str(e)}"


class UpdateUserFactTool(BaseTool):
    """
    Tool for updating an existing user fact.
    """
    
    name = "update_user_fact"
    summary = "Update a saved user fact by key. Use when user requests to modify their saved information."
    category = "user_data"
    description = """Update an existing user fact by key with a new value. Use ONLY when user explicitly requests to change their saved info (keywords: "update", "change", "modify"; examples: "Change my age to 30", "Update my name to Bao Do"). Key must already exist, otherwise returns error; returns confirmation with updated key-value."""
    
    def execute(self, key: str, value: str) -> str:
        """
        Update an existing user fact.
        
        Args:
            key: Fact key to update
            value: New value
            
        Returns:
            Success or error message
        """
        try:
            # Get user_id from context
            user_id = get_current_user_id()
            db = get_current_db_session()
            if not user_id:
                return "Error: Cannot determine user_id. Please log in again."
            
            if not key or not key.strip():
                return "Error: Key cannot be empty."
            
            if not value or not value.strip():
                return "Error: Value cannot be empty."
            
            key_clean = key.strip()
            value_clean = value.strip()
            
            # Check if fact exists
            facts = load_user_facts(user_id, db)
            fact = find_fact_by_key(facts, key_clean)
            
            if not fact:
                return f"No information found for key: {key_clean}. Use add_user_fact to add new."
            
            # Update fact
            fact_to_update: UserFact = {
                "user_id": user_id,
                "key": key_clean,
                "value": value_clean,
            }
            saved_fact = upsert_user_fact(fact_to_update, db)
            if saved_fact:
                return f"Updated: {key_clean} = {value_clean}"
            else:
                return "Error: Failed to save information."
                    
        except Exception as e:
            return f"Error updating user fact: {str(e)}"


class DeleteUserFactTool(BaseTool):
    """
    Tool for deleting a user fact.
    """
    
    name = "delete_user_fact"
    summary = "Forget/Delete a saved user fact by key. Use when user requests to forget/remove their saved information."
    category = "user_data"
    description = """Delete a saved user fact by key from long-term memory. Use when user explicitly requests to remove or forget their info (keywords: "delete", "forget", "remove"; examples: "Delete my name", "Forget my age", "Remove my address"). NEVER auto-delete; returns confirmation or error if key not found."""
    
    def execute(self, key: str) -> str:
        """
        Delete a user fact.
        
        Args:
            key: Fact key to delete
            
        Returns:
            Success or error message
        """
        try:
            # Get user_id from context
            user_id = get_current_user_id()
            db = get_current_db_session()
            if not user_id:
                return "Error: Cannot determine user_id. Please log in again."
            
            if not key or not key.strip():
                return "Error: Key cannot be empty."
            
            key_clean = key.strip()
            
            # Check if fact exists
            facts = load_user_facts(user_id, db)
            fact = find_fact_by_key(facts, key_clean)
            
            if not fact:
                return f"No information found for key: {key_clean}"
            
            # Delete fact
            if delete_user_fact_repo(user_id, key_clean, db):
                return f"Deleted: {key_clean}"
            else:
                return "Error: Failed to delete information."
                    
        except Exception as e:
            return f"Error deleting user fact: {str(e)}"
