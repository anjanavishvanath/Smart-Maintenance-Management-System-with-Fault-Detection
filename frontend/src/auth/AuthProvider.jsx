import React, { createContext, useState, useEffect, useContext } from 'react';
import api from '../api';
import tokenService from '../utils/tokenHelpers';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    //helper to decode JWT payload safely
    const parseJwt = (token) => {
        try {
            const payload = token.split('.')[1];  //token =header.payload.signature. get payload part
            return JSON.parse(atob(payload));
        } catch (e) {
            return null;
        }
    }

    useEffect(() => {
        const accessToken = tokenService.getAccess();
        if (accessToken) {
            const payload = parseJwt(accessToken); //get user info
            console.log(`payload:`, payload);
            if (payload) setUser({
                id: parseInt(payload.sub),
                email: payload.email,
                username: payload.username,
                role: payload.role,
                organization: payload.organization
            });
        }
        setLoading(false);
    }, []);

    // signup function
    async function signup(username, email, password, role = "technician", organization = null) {
        await api.post('/auth/signup', { username, email, password, role, organization });
    }

    async function login(email, password) {
        const res = await api.post('/auth/login', { email, password });
        tokenService.setTokens({
            access_token: res.data.access_token,
            refresh_token: res.data.refresh_token
        });
        const payload = parseJwt(res.data.access_token);
        setUser({
            id: parseInt(payload.sub),
            email: payload.email,
            username: payload.username,
            role: payload.role,
            organization: payload.organization
        });
        return res.data;
    }

    async function logout() {
        // Tell the backend to blocklist both tokens before we drop them locally.
        // If the network call fails (offline, expired token, server error) we still
        // clear local state — the user's intent is to log out.
        try {
            const refresh = tokenService.getRefresh();
            await api.post('/auth/logout', refresh ? { refresh_token: refresh } : {});
        } catch (e) {
            console.warn("Backend logout failed; clearing local session anyway.", e);
        }
        tokenService.clearTokens();
        setUser(null);
    }

    return (
        <AuthContext.Provider value={{ user, loading, signup, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}
// name hood for convinient consumption
export function useAuth() {
    return useContext(AuthContext);
}
