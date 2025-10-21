const ACCESS_KEY = "cm_access_token";
const REFRESH_KEY = "cm_refresh_token";

export const tokenService = {
    getAccess: () => localStorage.getItem(ACCESS_KEY),
    getRefresh: () => localStorage.getItem(REFRESH_KEY),
    setTokens: ({ access_token, refresh_token}) => {
        if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
        if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
    },
    clear: () => {
        localStorage.removeItem(ACCESS_KEY);
        localStorage.removeItem(REFRESH_KEY);
    }
};

    //centralized token storage helper function so api and AuthProvider can use the same resource 