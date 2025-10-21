// Axios instance with basic refresh on 401
import axios from "axios";
import { tokenService } from "./services/tokenService";


//create a custom axios instance with default config so we dont have to in every call
const api = axios.create({
    baseURL: "http://localhost:5000/api", // Vite dev server proxy or docker setup should route /api -> backend
    timeout: 10000
});

// attach access token before each request if available
//this makes every get and post call authenticated without manually doing it eveytime
api.interceptors.request.use(config => {
    const access = tokenService.getAccess();
    if (access) config.headers.Authorization = `Bearer ${access}`;
    return config;
});

//response interceptor: try to refrsh once on 401
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) prom.reject(error);
        else prom.resolve(token);
    });
    failedQueue = [];
};

// automatic token refresh logic
api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config;
    //check if request is 401 (unauthenticated) and ensures the request is not already a retry (to avoid infinite loop)
    if (err.response && err.response.status === 401 && !original._retry) {
      original._retry = true;
      //token refresh in progress. isRefreshing flag ensures only one refresh at a time. All other requests added to failedQueue
      if (isRefreshing) {
        // queue and wait
        return new Promise(function(resolve, reject){
          failedQueue.push({resolve, reject});
        }).then(token => {
          original.headers.Authorization = "Bearer " + token;
          return api(original);
        }).catch(e => Promise.reject(e));
      }

      isRefreshing = true;
      try {
        const refresh = tokenService.getRefresh();
        if (!refresh) throw new Error("no refresh token");
        // special unintercepted call to refresh endpoint using raw axios to avoid infinite loop
        const r = await axios.post("/api/auth/refresh", {}, {
          headers: { Authorization: `Bearer ${refresh}` },
          baseURL: "/"
        });
        const newAccess = r.data.access_token;
        tokenService.setTokens({ access_token: newAccess }); //handle success by storing new access token
        processQueue(null, newAccess); //retry all failed requests
        original.headers.Authorization = `Bearer ${newAccess}`; 
        return api(original); //retry original request with new token
      } catch (e) {
        processQueue(e, null);
        tokenService.clear(); //on failure clear stored tokens (logout)
        return Promise.reject(e);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(err);
  }
);

export default api;