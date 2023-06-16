import React from "react";
import ReactDOM from "react-dom/client";



import Map, {
  Marker,

} from "react-map-gl/maplibre";


import { LngLatBounds } from "maplibre-gl";;

// import VehicleMarker from "./VehicleMarker";
// import VehiclePopup from "./VehiclePopup";
// import Header from "./Header";
// import Sidebar from "./Sidebar";
import "./vehiclemarker.css";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

function getBounds(items) {
  let bounds = new LngLatBounds();
  for (let item of items) {
    bounds.extend([item.coordinates[0], item.coordinates[1]]);
  }
  debugger;
  return bounds;
}



function VehicleMarker(props) {
  let className = 'vehicle-marker';

  let rotation = props.vehicle.heading;

  if (rotation != null) {
    if (rotation < 180) {
      rotation -= 90;
      className += ' right';
    } else {
      rotation -= 270;
    }
  }

  if (props.vehicle.vehicle.livery) {
    className += ' livery-' + props.vehicle.vehicle.livery;
  }

  let css = props.vehicle.vehicle.css;
  if (css) {
    css = {
      background: css
    };
    if (props.vehicle.vehicle.text_colour) {
        className += ' white-text';
      }
  }

  return (
    <Marker
      latitude={props.vehicle.coordinates[1]}
      longitude={props.vehicle.coordinates[0]}
      rotation={rotation}
      onClick={() => props.onClick(props.vehicle.id)}
    >
      <div
        className={className}
        style={css}
      >
        <div className="text">{props.vehicle.service?.line_name}</div>
        { rotation == null ? null : <div className='arrow' /> }
      </div>
    </Marker>
  );
}


  const loadVehicles = () => {
  };


function OperatorMap() {

  // dark mode:

  const [darkMode, setDarkMode] = React.useState(false);

  React.useEffect(() => {
    if (window.matchMedia) {
      let query = window.matchMedia('(prefers-color-scheme: dark)');
      if (query.matches) {
        setDarkMode(true);
      }

      const handleChange = (e) => {
        console.log("handle");
        setDarkMode(e.matches);
      }

      console.log("add");
      query.addEventListener("change", handleChange);

      return () => {
        console.log("remove");
        query.removeEventListener("change", handleChange)
      };
    }
  }, []);


  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);


  const [bounds, setBounds] = React.useState(null);


  React.useEffect(() => {
    let url = apiRoot + "vehicles.json?operator=" + window.OPERATOR_ID;
    fetch(url).then((response) => {
      response.json().then((items) => {

        setBounds(getBounds(items));

        setVehicles(
          Object.assign({}, ...items.map((item) => ({[item.id]: item})))
        );
        setLoading(false);

      });
    });
  }, []);



  if (loading) {
    return "Loading…";
  }

  return (
    <Map

    dragRotate={false}
    touchPitch={false}
    touchRotate={false}
    pitchWithRotate={false}

    // onLoad={loadVehicles}

    minZoom={6}
    maxZoom={16}

    bounds={bounds}

    mapStyle={
        darkMode ?
        "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json" :
        "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      // )
    }

    // onClick={onClick}

    hash={true}

    RTLTextPlugin={null}
    // mapLib={maplibregl}

    >

      { Object.values(vehicles).map((item) => {
        return (
          <VehicleMarker
          key={item.id}
          vehicle={item}
          />
        );
      }) }

    </Map>
  );
}


const root = ReactDOM.createRoot(document.getElementById("map"));
root.render(
  <React.StrictMode>
    <OperatorMap/>
  </React.StrictMode>
);
