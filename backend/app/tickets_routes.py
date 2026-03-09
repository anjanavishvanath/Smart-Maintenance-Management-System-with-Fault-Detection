from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt
from db import create_ticket as db_create_ticket, get_tickets_by_org, get_assignable_users, delete_ticket, update_ticket_status

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
    return jsonify({'message': 'Ticket created successfully'}), 201

def get_org_tickets():
    # Fetch tickets filtered by the user's organization
    # This ensures Managers see everything in their company
    claims = get_jwt()
    organization = claims.get('organization')
    tickets = get_tickets_by_org(organization)
    return jsonify(tickets), 200

def get_assignable_users_route():
    claims = get_jwt()
    organization = claims.get('organization')
    role = claims.get('role')
    
    users = get_assignable_users(organization, role)
    return jsonify(users), 200

def delete_ticket_route(ticket_id):
    current_user_id = get_jwt_identity()
    if not current_user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    success = delete_ticket(int(ticket_id), int(current_user_id))
    if success:
        return jsonify({"message": "Ticket deleted successfully."}), 200
    else:
        return jsonify({"error": "Ticket not found or unauthorized."}), 404

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
        return jsonify({"message": f"Ticket status updated to {status}."}), 200
    else:
        return jsonify({"error": "Failed to update ticket status."}), 404
