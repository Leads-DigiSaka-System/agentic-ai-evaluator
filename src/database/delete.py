# delete.py
from qdrant_client.http import models
from src.generator.qdrant_load import client,DEMO_COLLECTION 


def delete_from_qdrant(form_id: str):
    """
    Delete a demo trial entry from Qdrant based on form_id.
    Must match payload field 'form_id'.
    """
    try:
        # Build filter
        filter_condition = models.Filter(
            must=[
                models.FieldCondition(
                    key="form_id",
                    match=models.MatchValue(value=form_id)
                )
            ]
        )

        # Perform delete
        response = client.delete(
            collection_name=DEMO_COLLECTION,
            points_selector=models.FilterSelector(filter=filter_condition)
        )

        return {
            "status": "success",
            "message": f"Deleted record with form_id: {form_id}",
            "response": str(response)
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to delete record with form_id: {form_id}",
            "error": str(e)
        }
