import React, {createContext, useContext, useState, useEffect} from 'react';
import api from '../api.js';
import { tokenService } from '../services/tokenService.js';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    //helper to decode JWT payload safely
    function parseJwt(token){
        try{
            const payload = token.split('.')[1]; //token =header.payload.signature. get payload part
            return JSON.parse(atob(payload));
        }catch {
            return null;
        }
    }
    
    useEffect(() => {
        const access = tokenService.getAccess();
        if(access) {
            const payload = parseJwt(access); //decode token to get user info
            if(payload) setUser({email: payload.email, username:payload.username, role: payload.role, sub: payload.sub});
        }
        setLoading(false);
    },[]);

    async function signup(username, email, password, role = "technician") {
        await api.post('/auth/signup', {username, email, password, role});
    }

    async function login(email, password) {
        const res = await api.post('/auth/login', {email, password});
        tokenService.setTokens({
            access_token: res.data.access_token,
            refresh_token: res.data.refresh_token,
        });
        const payload = parseJwt(res.data.access_token);
        setUser({email: payload.email, username:payload.username, role: payload.role, sub: payload.sub});
        return res.data;
    }

    function logout() {
        tokenService.clear();
        setUser(null);
    }

    return (
        <AuthContext.Provider value={{user, loading, signup, login, logout}}>
            {children}
        </AuthContext.Provider>
    )
}

//named hood for convinient consumption
export function useAuth() {
  return useContext(AuthContext);
}
