import axios from 'axios';
import tokenService from './utils/tokenHelpers';

const api = axios.create({
    baseURL: "http://localhost:5000/api",
    timeout: 10000
})

// attaching access token to each request if available so we don't have to do it manually every time
api.interceptors.request.use(config => {
    const access = tokenService.getAccess();
    if (access) config.headers.Authorization = `Bearer ${access}`;
    return config;
});

// response interceptor: try refreshing once on 401
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) prom.reject(error);
        else prom.resolve(token);
    });
    failedQueue = [];
};

// Automatic token refresh logic
api.interceptors.response.use(
    res => res,
    async err => {
        const originalRequest = err.config;
        //check if request is 401 (unauthenticated) and ensures the request is not already a retry (to avoid infinite loop)
        if (err.response && err.response.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            //token refresh in progress. isRefreshing flag ensures only one refresh at a time. All other requests added to failedQueue
            if (isRefreshing) {
                // queue and wait
                return new Promise(function (resolve, reject) {
                    failedQueue.push({ resolve, reject });
                }).then(token => {
                    originalRequest.headers.Authorization = 'Bearer ' + token;
                    return api(originalRequest);
                }).catch(e => Promise.reject(e));
            }
            isRefreshing = true;
            try {
                const refreshToken = tokenService.getRefresh();
                if (!refreshToken) throw new Error("No refresh token available");
                // special unintercepted call to refresh endpoint using raw axios to avoid infinite loop
                const r = await axios.post("/api/auth/refresh", {}, {
                    headers: { Authorization: `Bearer ${refreshToken}` },
                    baseURL: "http://localhost:5000"
                });
                const newAccessToken = r.data.access_token;
                tokenService.setTokens({ access_token: newAccessToken }); //handle success by storing new access token
                processQueue(null, newAccessToken); //retry all failed requests
                originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
                return api(originalRequest); //retry original request with new token
            } catch (e) {
                processQueue(e, null); //refresh failed. reject all queued requests
                return Promise.reject(e);
            } finally {
                isRefreshing = false;
            }
        }
        return Promise.reject(err);
    }
);

export default api;