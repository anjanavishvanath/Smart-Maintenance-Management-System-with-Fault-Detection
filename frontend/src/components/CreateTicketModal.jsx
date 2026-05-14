import { useState, useEffect } from "react";
import { toast } from "react-toastify";
import { maintenanceService } from "../utils/maintenanceService";

export default function CreateTicketModal({ onClose, onSuccess, initialData = {} }) {
    const [assignableUsers, setAssignableUsers] = useState([]);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [formData, setFormData] = useState({
        asset_id: initialData.asset_id || '',
        event_id: initialData.event_id || null,
        title: initialData.title || "",
        description: "",
        priority: initialData.priority || 2,
        assigned_to: "",
        due_date: ""
    });

    useEffect(() => {
        const fetchUsers = async () => {
            try {
                const users = await maintenanceService.getAssignableUsers();
                setAssignableUsers(users);
            } catch (err) {
                console.error("Failed to load assignable users", err);
            }
        };
        fetchUsers();
    }, []);

    // Close on Escape key
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [onClose]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            // Nullify empty strings for DB constraints
            const submissionData = { ...formData };
            if (!submissionData.assigned_to) submissionData.assigned_to = null;
            if (!submissionData.due_date) submissionData.due_date = null;

            await maintenanceService.createTicket(submissionData);
            onSuccess();
            onClose();
        } catch (error) {
            console.error("Failed to create ticket", error);
            toast.error("Failed to create ticket.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="modalOverlayStyle">
            <div className="modalContentStyle">
                <h2>Raise Maintenance Ticket</h2>
                <form onSubmit={handleSubmit}>
                    {!initialData.asset_id && (
                        <div className="form-group">
                            <label>Asset ID</label>
                            <input
                                required
                                type="number"
                                value={formData.asset_id}
                                onChange={e => setFormData({ ...formData, asset_id: parseInt(e.target.value) || '' })}
                                placeholder="Enter Asset ID"
                            />
                        </div>
                    )}
                    <div className="form-group">
                        <label>Title</label>
                        <input
                            required
                            type="text"
                            value={formData.title}
                            onChange={e => setFormData({ ...formData, title: e.target.value })}
                            placeholder="e.g., High Vibration on Main Motor"
                        />
                    </div>
                    <div className="form-group">
                        <label>Priority</label>
                        <select
                            value={formData.priority}
                            onChange={e => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                        >
                            <option value={1}>Low (Routine)</option>
                            <option value={2}>Medium (Precautionary)</option>
                            <option value={3}>High (Urgent)</option>
                            <option value={4}>Critical (Immediate Action)</option>
                        </select>
                    </div>

                    {assignableUsers.length > 0 && (
                        <div className="form-group">
                            <label>Assign To</label>
                            <select
                                value={formData.assigned_to}
                                onChange={e => setFormData({ ...formData, assigned_to: e.target.value ? parseInt(e.target.value) : '' })}
                            >
                                <option value="">Unassigned</option>
                                {assignableUsers.map(user => (
                                    <option key={user.id} value={user.id}>
                                        {user.username} ({user.role})
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div className="form-group">
                        <label>Due Date</label>
                        <input
                            type="date"
                            value={formData.due_date}
                            onChange={e => setFormData({ ...formData, due_date: e.target.value })}
                        />
                    </div>

                    <div className="form-group">
                        <label>Description</label>
                        <textarea
                            rows="4"
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                        />
                    </div>
                    <div className="modal-actions">
                        <button type="button" className="btn" onClick={onClose} disabled={isSubmitting}>Cancel</button>
                        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                            {isSubmitting ? 'Creating...' : 'Create Ticket'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};