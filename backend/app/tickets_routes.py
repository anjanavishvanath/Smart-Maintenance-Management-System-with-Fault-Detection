from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt
from db import (
    create_ticket as db_create_ticket,
    get_tickets_by_org,
    get_assignable_users,
    delete_ticket,
    update_ticket_status,
    write_audit_log,
)

def create_ticket():
    data = request.get_json()
    asset_id = data.get('asset_id')
    event_id = data.get('event_id')
    
    current_user_id = get_jwt_identity()
    created_by = int(current_user_id) if current_user_id else None
    
    assigned_to = data.get('assigned_to')
    title = data.get('title')
    description = data.get('description')
    priority = data.get('priority')
    due_date = data.get('due_date')
    status = data.get('status', 'open') # Default to 'open'
    
    db_create_ticket(asset_id, event_id, created_by, assigned_to, title, description, priority, due_date, status)
    claims = get_jwt() or {}
    write_audit_log(
        user_id=created_by, organization=claims.get("organization"),
        action="ticket.create", entity="ticket",
        metadata={
            "asset_id": asset_id, "event_id": event_id,
            "title": title, "priority": priority, "assigned_to": assigned_to,
        },
    )
    return jsonify({'message': 'Ticket created successfully'}), 201

def get_org_tickets():
    """Paginated list of tickets in the caller's organization."""
    claims = get_jwt()
    organization = claims.get('organization')
    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0
    tickets = get_tickets_by_org(organization, limit=limit, offset=offset)
    return jsonify(tickets), 200

def get_assignable_users_route():
    claims = get_jwt()
    organization = claims.get('organization')
    role = claims.get('role')
    
    users = get_assignable_users(organization, role)
    return jsonify(users), 200

def delete_ticket_route(ticket_id):
    """
    Delete a ticket honouring RBAC:
      - manager: any ticket in their organization
      - engineer/technician: only own tickets, only when status='open'
    """
    current_user_id = get_jwt_identity()
    if not current_user_id:
        return jsonify({"error": "Unauthorized"}), 401

    claims = get_jwt() or {}
    role = claims.get("role")
    organization = claims.get("organization")

    success, reason = delete_ticket(int(ticket_id), int(current_user_id), role, organization)
    if success:
        write_audit_log(
            user_id=int(current_user_id), organization=organization,
            action="ticket.delete", entity="ticket", entity_id=ticket_id,
        )
        return jsonify({"message": "Ticket deleted successfully."}), 200

    # Map the reason to the right HTTP status.
    if reason == "Ticket not found":
        return jsonify({"error": reason}), 404
    if reason in ("Ticket does not belong to your organization", "You don't have permission to delete this ticket"):
        return jsonify({"error": reason}), 403
    return jsonify({"error": reason or "Failed to delete ticket"}), 400

def update_ticket_status_route(ticket_id):
    current_user_id = get_jwt_identity()
    if not current_user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    status = data.get('status')
    if not status:
        return jsonify({"error": "Status is required"}), 400

    success = update_ticket_status(int(ticket_id), status, int(current_user_id))
    if success:
        claims = get_jwt() or {}
        write_audit_log(
            user_id=int(current_user_id), organization=claims.get("organization"),
            action="ticket.status_change", entity="ticket", entity_id=ticket_id,
            metadata={"new_status": status},
        )
        return jsonify({"message": f"Ticket status updated to {status}."}), 200
    else:
        return jsonify({"error": "Failed to update ticket status."}), 404
