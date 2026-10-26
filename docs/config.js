// Where the API lives.
//   On GitHub Pages            -> the shared cloud API (Render).
//   Opened from start.bat      -> the same laptop server (http://127.0.0.1:8000), works offline.
// After deploying to Render, put its URL here (no trailing slash).
window.MESS_CLOUD_API = "";  // e.g. "https://mess-api-xxxx.onrender.com"

window.MESS_API_DEFAULT = location.hostname.endsWith("github.io")
  ? window.MESS_CLOUD_API
  : location.protocol.startsWith("http") ? location.origin : "http://127.0.0.1:8000";

// SMS login (Firebase Phone Auth). Firebase console -> Project settings -> Your apps -> Web app -> config.
// These values are meant to be public; Firebase only accepts them from the domains you authorize.
// The API reads projectId from this file too, so this is the only place to set it.
window.MESS_FIREBASE = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  appId: "",
};
