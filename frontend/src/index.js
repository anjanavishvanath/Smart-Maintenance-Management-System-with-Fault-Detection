import React from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";

function App() {
    const [last, setLast] = React.useState(null);
    React.useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const r = await axios.get("/api/last");
                setLast(r.data);
            }catch (e) {
                console.log(e);
            }
        }, 1500);
        return () => clearInterval(interval);
    }, []);

    return (
        <div style={{padding: 20}}>
            <h2>CM System - Demo Frontend</h2>
            <p>Polling backend for last mqtt message...</p>
            <pre>{JSON.stringify(last, null, 2)}</pre>
        </div>
    );
}

createRoot(document.getElementById("root")).render(<App />);