"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all currently active announcements (publicly accessible)
    
    Returns announcements where:
    - start_date is None or in the past
    - end_date is in the future
    """
    now = datetime.now().isoformat()
    
    query = {
        "$and": [
            {"end_date": {"$gte": now}},
            {
                "$or": [
                    {"start_date": None},
                    {"start_date": {"$lte": now}}
                ]
            }
        ]
    }
    
    announcements = []
    for announcement in announcements_collection.find(query).sort("created_at", -1):
        announcement["_id"] = str(announcement["_id"])
        announcements.append(announcement)
    
    return announcements


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """
    Get all announcements (active and expired) - requires teacher authentication
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    announcements = []
    for announcement in announcements_collection.find().sort("created_at", -1):
        announcement["_id"] = str(announcement["_id"])
        announcements.append(announcement)
    
    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    end_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Create a new announcement - requires teacher authentication
    
    - message: The announcement message text
    - end_date: Required expiration date (ISO format)
    - start_date: Optional start date (ISO format)
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    # Validate dates
    try:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if start_dt >= end_dt:
                raise HTTPException(
                    status_code=400, detail="Start date must be before end date")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    # Create announcement
    announcement = {
        "message": message,
        "start_date": start_date,
        "end_date": end_date,
        "created_by": teacher_username,
        "created_at": datetime.now().isoformat()
    }
    
    result = announcements_collection.insert_one(announcement)
    announcement["_id"] = str(result.inserted_id)
    
    return announcement


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: Optional[str] = None,
    end_date: Optional[str] = None,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Update an existing announcement - requires teacher authentication
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    # Find the announcement
    try:
        announcement = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Build update dict
    update_fields = {}
    if message is not None:
        update_fields["message"] = message
    if end_date is not None:
        try:
            datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            update_fields["end_date"] = end_date
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid end_date format. Use ISO format")
    if start_date is not None:
        if start_date == "":
            update_fields["start_date"] = None
        else:
            try:
                datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                update_fields["start_date"] = start_date
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid start_date format. Use ISO format")
    
    # Validate date logic
    final_start = update_fields.get("start_date", announcement.get("start_date"))
    final_end = update_fields.get("end_date", announcement.get("end_date"))
    
    if final_start and final_end:
        try:
            start_dt = datetime.fromisoformat(final_start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(final_end.replace('Z', '+00:00'))
            if start_dt >= end_dt:
                raise HTTPException(
                    status_code=400, detail="Start date must be before end date")
        except ValueError:
            pass  # Already validated individual dates
    
    if update_fields:
        announcements_collection.update_one(
            {"_id": ObjectId(announcement_id)},
            {"$set": update_fields}
        )
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    updated["_id"] = str(updated["_id"])
    
    return updated


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """
    Delete an announcement - requires teacher authentication
    """
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")
    
    # Delete the announcement
    try:
        result = announcements_collection.delete_one({"_id": ObjectId(announcement_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
