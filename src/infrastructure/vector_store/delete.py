# delete.py
from qdrant_client.http import models
from src.infrastructure.embeddings.qdrant_load import client, DEMO_COLLECTION
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)
def delete_from_qdrant(form_id: str, user_id: str = None):
    """
    Delete a demo trial entry from Qdrant based on form_id with user_id validation.
    Must match payload field 'form_id' and optionally 'user_id' for security.
    
    Args:
        form_id: Unique identifier for the form to delete
        user_id: Optional user ID - if provided, only deletes if form belongs to that user
        
    Returns:
        dict: Status and details of the deletion operation
    """
    try:
        # Build filter conditions
        filter_conditions = [
            models.FieldCondition(
                key="form_id",
                match=models.MatchValue(value=form_id)
            )
        ]
        
        # ✅ Add user_id filter for security (if provided)
        if user_id:
            filter_conditions.append(
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id)
                )
            )
        
        filter_condition = models.Filter(must=filter_conditions)

        # Perform delete
        response = client.delete(
            collection_name=DEMO_COLLECTION,
            points_selector=models.FilterSelector(filter=filter_condition)
        )

        if user_id:
            logger.info(f"Deleted record with form_id: {form_id} for user: {user_id}")
        else:
            logger.info(f"Deleted record with form_id: {form_id}")

        return {
            "status": "success",
            "message": f"Deleted record with form_id: {form_id}",
            "response": str(response)
        }

    except Exception as e:
        logger.error(f"Failed to delete record with form_id: {form_id} - {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to delete record with form_id: {form_id}",
            "error": str(e)
        }


# ✅ NEW FUNCTION: Delete all records in a collection
def delete_all_from_collection(collection_name: str):
    """
    Delete ALL records from a specified Qdrant collection.
    
    ⚠️ WARNING: This is destructive! All data in the collection will be lost.
    
    Args:
        collection_name: Name of the collection to clear
        
    Returns:
        dict: Status and details of the deletion operation
    """
    try:
        # Get collection info first to verify it exists and count points
        try:
            collection_info = client.get_collection(collection_name=collection_name)
            point_count = collection_info.points_count
            logger.info(f"Collection '{collection_name}' has {point_count} points")
        except Exception as e:
            logger.error(f"Collection '{collection_name}' not found")
            return {
                "status": "error",
                "message": f"Collection '{collection_name}' does not exist",
                "error": str(e)
            }
        
        if point_count == 0:
            logger.info(f"Collection '{collection_name}' is already empty")
            return {
                "status": "success",
                "message": f"Collection '{collection_name}' is already empty",
                "deleted_count": 0
            }
        
        # Delete all points by using an empty filter (matches everything)
        logger.warning(f"DELETING ALL {point_count} points from collection '{collection_name}'...")
        
        response = client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[]  # Empty filter = match all points
                )
            )
        )
        
        # Verify deletion
        collection_info_after = client.get_collection(collection_name=collection_name)
        remaining_points = collection_info_after.points_count
        
        if remaining_points == 0:
            logger.info(f"Successfully deleted all {point_count} points from '{collection_name}'")
            return {
                "status": "success",
                "message": f"Successfully deleted all records from collection '{collection_name}'",
                "deleted_count": point_count,
                "remaining_count": remaining_points,
                "response": str(response)
            }
        else:
            logger.warning(f"Deletion incomplete. {remaining_points} points remaining")
            return {
                "status": "partial_success",
                "message": f"Deleted some records, but {remaining_points} points remain",
                "deleted_count": point_count - remaining_points,
                "remaining_count": remaining_points,
                "response": str(response)
            }

    except Exception as e:
        logger.error(f"Failed to delete all records from '{collection_name}': {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Failed to delete all records from collection '{collection_name}'",
            "error": str(e)
        }