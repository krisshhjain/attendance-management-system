/**
 * Geolocation utility to request device coordinates.
 * Returns a promise resolving with { latitude, longitude, accuracy }.
 */
export function getCurrentCoordinates() {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined" || !navigator.geolocation) {
      const err = new Error("Geolocation is not supported by your browser or device.");
      err.code = "NOT_SUPPORTED";
      return reject(err);
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
        });
      },
      (error) => {
        let message = "Unable to retrieve your location. Please try again.";
        // GeolocationPositionError codes:
        // 1: PERMISSION_DENIED
        // 2: POSITION_UNAVAILABLE
        // 3: TIMEOUT
        if (error.code === 1) {
          message = "Location permission is required to mark attendance. Please allow location access and try again.";
        } else if (error.code === 2) {
          message = "Location information is unavailable. Please check your device location settings and try again.";
        } else if (error.code === 3) {
          message = "Location request timed out. Please check your device connection and try again.";
        }
        const err = new Error(message);
        err.code = error.code;
        reject(err);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  });
}
