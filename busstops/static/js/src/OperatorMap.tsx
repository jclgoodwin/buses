import React from "react";

import Map, {
  NavigationControl,
  GeolocateControl,
  MapEvent,
} from "react-map-gl/maplibre";

import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import { useDarkMode, getBounds } from "./utils";

const apiRoot = process.env.API_ROOT;

type OperatorMapProps = {
  noc: string;
};

export default function OperatorMap({ noc }) {
  const darkMode = useDarkMode();

  const [vehicles, setVehicles] = React.useState(null);

  const [bounds, setBounds] = React.useState(null);

  React.useEffect(() => {
    let timeout: number;

    const loadVehicles = (first = false) => {
      if (document.hidden && !first) {
        return;
      }

      let url = apiRoot + "vehicles.json?operator=" + noc;
      fetch(url).then((response) => {
        response.json().then((items) => {
          if (first) {
            setBounds(getBounds(items));
          }

          setVehicles(
            Object.assign({}, ...items.map((item) => ({ [item.id]: item }))),
          );
          clearTimeout(timeout);
          if (!document.hidden) {
            timeout = setTimeout(loadVehicles, 10000); // 10 seconds
          }
        });
      });
    };

    loadVehicles(true);

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

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleMapClick = React.useCallback((e) => {
    const srcElement = e.originalEvent.srcElement;
    const vehicleId =
      srcElement.dataset.vehicleId || srcElement.parentNode.dataset.vehicleId;
    if (vehicleId) {
      setClickedVehicleMarker(vehicleId);
    } else {
      setClickedVehicleMarker(null);
    }
  }, []);

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
  }, []);

  if (!vehicles) {
    return <div className="sorry">Loading…</div>;
  }

  const vehiclesList = Object.values(vehicles);

  if (!vehiclesList.length) {
    return (
      <div className="sorry">Sorry, no buses are tracking at the moment</div>
    );
  }

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  // const clickedTripId = clickedVehicle?.trip_id;

  return (
    <React.Fragment>
      <div className="operator-map">
        <Map
          dragRotate={false}
          touchPitch={false}
          pitchWithRotate={false}
          maxZoom={18}
          bounds={bounds}
          fitBoundsOptions={{
            maxZoom: 15,
            padding: 50,
          }}
          mapStyle={
            darkMode
              ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
              : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
          }
          RTLTextPlugin={null}
          onClick={handleMapClick}
          onLoad={handleMapLoad}
        >
          <NavigationControl showCompass={false} />
          <GeolocateControl />

          {vehiclesList.map((item) => {
            return (
              <VehicleMarker
                key={item.id}
                selected={item.id === clickedVehicleMarkerId}
                vehicle={item}
              />
            );
          })}

          {clickedVehicle && (
            <VehiclePopup
              item={clickedVehicle}
              onClose={() => setClickedVehicleMarker(null)}
            />
          )}
        </Map>
      </div>
      {/*{clickedTripId ? <TripLayer tripId={clickedTripId} /> : null}*/}
    </React.Fragment>
  );
}
