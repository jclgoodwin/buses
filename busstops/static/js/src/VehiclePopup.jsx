import React, { memo } from "react";
import { Popup } from "react-map-gl/maplibre";
import ReactTimeAgo from "react-time-ago";

import TimeAgo from "javascript-time-ago";

import en from "javascript-time-ago/locale/en.json";
TimeAgo.addDefaultLocale(en);

function getTimeDelta(seconds) {
  const minutes = Math.round(seconds / 60);
  if (minutes === 1) {
    return "1 minute";
  }
  return minutes + " minutes";
}

function Delay({ item }) {
  if (typeof delay !== "undefined") {
    let delay = item.delay;
    if (-60 < delay && delay < 60) {
      delay = "On time";
    } else {
      if (delay < 0) {
        delay *= -1;
      }
      delay = getTimeDelta(delay);
      if (item.delay < 0) {
        delay += " early";
      } else {
        delay += " late";
      }
    }
    return <div>{delay}</div>;
  }
}

function VehiclePopup({ item, onClose }) {
  let line_name = item.service?.line_name;
  if (item.destination) {
    if (line_name) {
      line_name += " to ";
    }
    line_name += item.destination;
  }

  if (item.trip_id) {
    line_name = <a href={`/trips/${item.trip_id}`}>{line_name}</a>;
  } else if (item.service?.url) {
    line_name = <a href={item.service.url}>{line_name}</a>;
  }

  let vehicle = item.vehicle.name;
  if (item.vehicle.url) {
    vehicle = <a href={`${item.vehicle.url}`}>{vehicle}</a>;
  }

  return (
    <Popup
      offset={8}
      latitude={item.coordinates[1]}
      longitude={item.coordinates[0]}
      closeOnClick={false}
      onClose={onClose}
    >
      <div>{line_name}</div>
      {vehicle}
      {item.vehicle.features && (
        <div>{item.vehicle.features.replace("<br>", ", ")}</div>
      )}
      {item.seats && (
        <div>
          <img alt="" src="/static/svg/seat.svg" width="14" height="14" />{" "}
          {item.seats}
        </div>
      )}
      {item.wheelchair && (
        <div>
          <img
            alt="wheelchair"
            src="/static/svg/wheelchair.svg"
            width="14"
            height="14"
          />{" "}
          {item.wheelchair}
        </div>
      )}
      <Delay item={item} />
      <div>
        <ReactTimeAgo date={item.datetime} locale="en-GB" tooltip={true} />
      </div>
    </Popup>
  );
}

function propsAreEqual(prev, props) {
  return (
    prev.item.id == props.item.id && prev.item.datetime === props.item.datetime
  );
}

export default memo(VehiclePopup, propsAreEqual);
