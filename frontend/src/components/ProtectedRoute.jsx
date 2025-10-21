import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider.jsx';

export default function ProtectedRoute({ redirectTo = '/login'}) {
    const { user, loading } = useAuth();
    if (loading) return <div>Loading...</div>;
    return user ? <Outlet /> : <Navigate to={redirectTo} replace />;
}