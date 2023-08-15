import React from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

import StopPopup from "./StopPopup";
import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import { useDarkMode } from "./utils";

const routeStyle = {
  type: "line",
  paint: {
    "line-color": "#777",
    "line-width": 3,
  },
};

export default function ServiceMapMap({
  vehicles,
  vehiclesList,
  geometry,
  stops,
  closeButton,
}) {
  const darkMode = useDarkMode();

  const [cursor, setCursor] = React.useState();

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
  }, []);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const [clickedStop, setClickedStop] = React.useState(null);

  const handleMapClick = React.useCallback(
    (e) => {
      const srcElement = e.originalEvent.srcElement;
      const vehicleId =
        srcElement.dataset.vehicleId || srcElement.parentNode.dataset.vehicleId;
      if (vehicleId) {
        setClickedStop(null);
        setClickedVehicleMarker(vehicleId);
        return;
      }

      if (e.features.length) {
        for (const stop of e.features) {
          if (stop.properties.url !== clickedStop?.properties.url) {
            setClickedStop(stop);
          }
        }
      } else {
        setClickedStop(null);
      }
      setClickedVehicleMarker(null);
    },
    [clickedStop],
  );

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    map.loadImage("/static/route-stop-marker.png", (error, image) => {
      if (error) throw error;
      map.addImage("stop", image, {
        pixelRatio: 2,
      });
    });
  }, []);

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  let popup = null;
  if (vehiclesList && vehiclesList.length === 1) {
    popup = (
      <VehiclePopup
        item={vehiclesList[0]}
        closeButton={false}
        onClose={() => {
          setClickedVehicleMarker(null);
        }}
      />
    );
  } else if (clickedVehicle) {
    popup = (
      <VehiclePopup
        item={clickedVehicle}
        onClose={() => {
          setClickedVehicleMarker(null);
        }}
      />
    );
  }

  const stopsStyle = {
    id: "stops",
    type: "symbol",
    layout: {
      "icon-rotate": ["+", 45, ["get", "bearing"]],
      "icon-image": "stop",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  };

  return (
    <Map
      dragRotate={false}
      touchPitch={false}
      touchRotate={false}
      pitchWithRotate={false}
      maxZoom={18}
      bounds={window.EXTENT}
      fitBoundsOptions={{
        padding: 20,
      }}
      cursor={cursor}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      mapStyle={
        darkMode
          ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
          : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      }
      RTLTextPlugin={null}
      onClick={handleMapClick}
      onLoad={handleMapLoad}
      interactiveLayerIds={["stops"]}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />

      {closeButton}

      {vehiclesList ? (
        vehiclesList.map((item) => {
          return (
            <VehicleMarker
              key={item.id}
              selected={item.id === clickedVehicleMarkerId}
              vehicle={item}
            />
          );
        })
      ) : (
        <div className="maplibregl-ctrl">Loading</div>
      )}

      {popup}

      {clickedStop ? (
        <StopPopup item={clickedStop} onClose={() => setClickedStop(null)} />
      ) : null}

      {geometry && (
        <Source type="geojson" data={geometry}>
          <Layer {...routeStyle} />
        </Source>
      )}

      {stops && (
        <Source type="geojson" data={stops}>
          <Layer {...stopsStyle} />
        </Source>
      )}
    </Map>
  );
}
