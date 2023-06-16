import React from "react";
import ReactDOM from "react-dom/client";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";
import StopPopup from "./StopPopup";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

function getBoundsQueryString(bounds) {
  return `?ymax=${bounds.getNorth()}&xmax=${bounds.getEast()}&ymin=${bounds.getSouth()}&xmin=${bounds.getWest()}`;
}

const stopsLayerStyle = {
  id: "stops",
  type: "circle",
  paint: {
    "circle-color": "#333",
    "circle-opacity": 0.6,
    "circle-radius": 4,
  },
};

function BigMap() {
  // dark mode:

  const [darkMode, setDarkMode] = React.useState(false);

  React.useEffect(() => {
    if (window.matchMedia) {
      let query = window.matchMedia("(prefers-color-scheme: dark)");
      if (query.matches) {
        setDarkMode(true);
      }

      const handleChange = (e) => {
        setDarkMode(e.matches);
      };

      query.addEventListener("change", handleChange);

      return () => {
        query.removeEventListener("change", handleChange);
      };
    }
  }, []);

  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  const [bounds, setBounds] = React.useState(null);

  const [stops, setStops] = React.useState(null);

  const [clickedStopId, setClickedStopId] = React.useState(null);

  const loadStops = React.useCallback((bounds) => {
    const url = apiRoot + "stops.json" + getBoundsQueryString(bounds);
    fetch(url).then((response) => {
      response.json().then((items) => {
        setStops(items);
        setStopsHighWaterMark(bounds);
      });
    });
  }, []);

  const [stopsHighWaterMark, setStopsHighWaterMark] = React.useState(null);

  const handleMoveEnd = (evt) => {
    const map = evt.target;
    const zoom = map.getZoom();
    if (zoom > 8) {
      const bounds = map.getBounds();

      if (
        zoom >= 13 &&
        !(
          stopsHighWaterMark?.contains(bounds.getNorthWest()) &&
          stopsHighWaterMark.contains(bounds.getSouthEast())
        )
      ) {
        loadStops(bounds);
      }
    }
  };

  /*
  React.useEffect(() => {
    const loadVehicles = () => {
      let url = apiRoot + "vehicles.json";
      fetch(url).then((response) => {
        response.json().then((items) => {

          setVehicles(
            Object.assign({}, ...items.map((item) => ({ [item.id]: item })))
          );
          setLoading(false);
          clearTimeout(timeout);
          timeout = setTimeout(loadVehicles, 10000); // 10 seconds
        });
      });
    };

    loadVehicles();

    const handleVisibilityChange = (event) => {
      if (event.target.hidden) {
        clearTimeout(timeout);
      } else {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimeout(timeout);
    };
  }, []);
  */

  /*
  let timeout;

  React.useEffect(() => {
    const loadVehicles = () => {
      let url = apiRoot + "vehicles.json";
      fetch(url).then((response) => {
        response.json().then((items) => {

          setVehicles(
            Object.assign({}, ...items.map((item) => ({ [item.id]: item })))
          );
          setLoading(false);
          clearTimeout(timeout);
          timeout = setTimeout(loadVehicles, 10000); // 10 seconds
        });
      });
    };

    loadVehicles();

    const handleVisibilityChange = (event) => {
      if (event.target.hidden) {
        clearTimeout(timeout);
      } else {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimeout(timeout);
    };
  }, []);
  */

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleVehicleMarkerClick = React.useCallback((event, id) => {
    event.originalEvent.preventDefault();
    setClickedVehicleMarker(id);
  }, []);

  const handleMapClick = React.useCallback((e) => {
    if (e.features.length) {
      setClickedStopId(e.features[0]);
    } else if (!e.originalEvent.defaultPrevented) {
      setClickedVehicleMarker(null);
    }
  }, []);

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
  }, []);

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  return (
    <Map
      initialViewState={{
        latitude: 53.45, // ireland
        longitude: -7.5,
        zoom: 6,
      }}
      dragRotate={false}
      touchPitch={false}
      touchRotate={false}
      pitchWithRotate={false}
      onMoveEnd={handleMoveEnd}
      minZoom={6}
      maxZoom={16}
      mapStyle={
        darkMode
          ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
          : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      }
      hash={true}
      RTLTextPlugin={null}
      onClick={handleMapClick}
      onLoad={handleMapLoad}
      interactiveLayerIds={["stops"]}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />

      <Source type="geojson" data={stops}>
        <Layer {...stopsLayerStyle} />
      </Source>

      {/*vehiclesList.map((item) => {
        return (
          <VehicleMarker
            key={item.id}
            selected={item.id === clickedVehicleMarkerId}
            vehicle={item}
            onClick={handleVehicleMarkerClick}
          />
        );
      })*/}

      {clickedVehicle && (
        <VehiclePopup
          item={clickedVehicle}
          onClose={() => setClickedVehicleMarker(null)}
        />
      )}

      {clickedStopId && (
        <StopPopup
          item={clickedStopId}
          onClose={() => setClickedStopId(null)}
        />
      )}
    </Map>
  );
}

const root = ReactDOM.createRoot(document.getElementById("hugemap"));
root.render(
  <React.StrictMode>
    <BigMap />
  </React.StrictMode>
);
