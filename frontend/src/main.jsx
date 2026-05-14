import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from "./auth/AuthProvider";
import ProtectedRoute from "./components/ProtectedRoute";
import AppLayout from "./AppLayout";
import "./index.css";
import Signup from "./pages/Signup";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import DeviceProvisioning from "./components/DeviceProvisioning";
import AssetPage from "./pages/AssetsPage";
import SensorsPage from "./pages/SensorsPage";
import MaintenancePage from "./pages/MaintenancePage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";

createRoot(document.getElementById("root")).render(
    <AuthProvider>
        <BrowserRouter>
            <Routes>
                <Route path='/' element={<AppLayout />}>
                    <Route index element={<Navigate to='/dashboard' replace />} />   {/* If not logged, protected route will redirect to login */}
                    <Route path='/signup' element={<Signup />} />
                    <Route path='/login' element={<Login />} />
                    <Route element={<ProtectedRoute />}>
                        <Route path='dashboard' element={<Dashboard />} />
                        <Route path='asset_registry' element={<AssetPage />} />
                        <Route path='sensor_registry' element={<SensorsPage />} />
                        <Route path='maintenance_registry' element={<MaintenancePage />} />
                        <Route path='reports' element={<ReportsPage />} />
                        <Route path='settings' element={<SettingsPage />} />
                    </Route>
                </Route>
            </Routes>
        </BrowserRouter>
    </AuthProvider>
);