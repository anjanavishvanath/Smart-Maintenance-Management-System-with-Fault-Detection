import React, {useState} from 'react';
import {Outlet, Link, useNavigate} from 'react-router-dom';
import { useAuth } from './auth/AuthProvider.jsx';
import logo from './assets/logo.svg';

export default function AppLayout() {

    const {user, logout} = useAuth();
    const nav = useNavigate();

    function onLogout(){
        logout();
        nav('/login');
    }
    return (
        <div>
            {user ? <nav>
                <img src={logo} alt="preSense Logo" className="logo" />
                <Link to="logout" onClick={onLogout}>Logout</Link>
            </nav> : null
            }
            <main>
                <Outlet />
            </main>
        </div>
    )
}