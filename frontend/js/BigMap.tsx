import React, { ReactElement, memo, useRef } from "react";

import {
  Source,
  Layer,
  MapProps,
  useMap,
  ViewStateChangeEvent,
  MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import { LngLatBounds, Map, Hash } from "maplibre-gl";
import { Link } from "wouter";

import debounce from "lodash/debounce";

import VehicleMarker, {
  Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";

import VehiclePopup from "./VehiclePopup";
import StopPopup, { Stop } from "./StopPopup";
import BusTimesMap from "./Map";
import { Route } from "./TripMap";
import TripTimetable, { Trip } from "./TripTimetable";

import { decodeTimeAwarePolyline } from "./time-aware-polyline";

const apiRoot = process.env.API_ROOT;

declare global {
  interface Window {
    INITIAL_VIEW_STATE: MapProps["initialViewState"];
  }
}

const updateLocalStorage = debounce(function (zoom: number, latLng) {
  try {
    localStorage.setItem("vehicleMap", `${zoom}/${latLng.lat}/${latLng.lng}`);
  } catch (e) {
    // never mind
  }
}, 2000);

if (window.INITIAL_VIEW_STATE && !window.location.hash) {
  try {
    if (localStorage.vehicleMap) {
      const parts = localStorage.vehicleMap.split("/");
      if (parts.length === 3) {
        window.INITIAL_VIEW_STATE = {
          zoom: parts[0],
          latitude: parts[1],
          longitude: parts[2],
        };
      }
    }
  } catch (e) {
    // never mind
  }
}

function getBoundsQueryString(bounds: LngLatBounds): string {
  return `?ymax=${bounds.getNorth()}&xmax=${bounds.getEast()}&ymin=${bounds.getSouth()}&xmin=${bounds.getWest()}`;
}

function containsBounds(
  a: LngLatBounds | undefined,
  b: LngLatBounds,
): boolean | undefined {
  return a && a.contains(b.getNorthWest()) && a.contains(b.getSouthEast());
}

function shouldShowStops(zoom?: number) {
  return zoom && zoom >= 14;
}

function shouldShowVehicles(zoom?: number) {
  return zoom && zoom >= 6;
}

export enum MapMode {
  Slippy,
  Operator,
  Trip,
  Journey,
}

type Journey = {
  id: number;
  datetime: string;
  vehicle: {
    id: number;
    slug: string;
    fleet_code: string;
    reg: string;
  };
  trip_id: number | null;
  times: Trip["times"];
  route_name: string;
  destination: string;
  time_aware_polyline: string;
};

type StopsProps = {
  stops?: {
    features: Stop[];
  };
  times?: Trip["times"];
  clickedStopUrl?: string;
  setClickedStop: (stop?: string) => void;
};

function SlippyMapHash() {
  const mapRef = useMap();

  React.useEffect(() => {
    if (mapRef.current) {
      const map = mapRef.current.getMap();
      let hash: Hash;
      if (!map._hash) {
        hash = new Hash();
        hash.addTo(map);
      }
      return () => {
        if (hash) {
          hash.remove();
        }
      };
    }
  }, [mapRef]);

  return null;
}

function Stops({ stops, times, clickedStopUrl, setClickedStop }: StopsProps) {
  const stopsById = React.useMemo<{ [url: string]: Stop } | undefined>(() => {
    if (stops) {
      return Object.assign(
        {},
        ...stops.features.map((stop) => ({ [stop.properties.url]: stop })),
      );
    }
    if (times) {
      return Object.assign(
        {},
        ...times.map((time) => {
          const url = "/stops/" + time.stop.atco_code;
          return {
            [url]: {
              properties: { url, name: time.stop.name },
              geometry: { coordinates: time.stop.location },
            },
          };
        }),
      );
    }
  }, [stops, times]);

  const clickedStop = stopsById && clickedStopUrl && stopsById[clickedStopUrl];

  return (
    <React.Fragment>
      {stops ? (
        <Source type="geojson" data={stops}>
          <Layer
            {...{
              id: "stops",
              type: "symbol",
              minzoom: 14,
              layout: {
                "text-field": ["get", "icon"],
                "text-font": ["Stadia Regular"],
                "text-allow-overlap": true,
                "text-size": 10,
                "icon-rotate": ["+", 45, ["get", "bearing"]],
                "icon-image": [
                  "case",
                  ["==", ["get", "bearing"], ["literal", null]],
                  "stop-marker-circle",
                  "stop-marker",
                ],
                "icon-allow-overlap": true,
                "icon-ignore-placement": true,
                "text-ignore-placement": true,
                "icon-padding": [3],
              },
              paint: {
                "text-color": "#ffffff",
              },
            }}
          />
        </Source>
      ) : null}
      {clickedStop ? (
        <StopPopup
          item={clickedStop}
          onClose={() => setClickedStop(undefined)}
        />
      ) : null}
    </React.Fragment>
  );
}

function fetchJson(url: string) {
  return fetch(apiRoot + url).then(
    (response) => {
      if (response.ok) {
        return response.json();
      }
    },
    () => {
      // never mind
    },
  );
}

type VehiclesProps = {
  vehicles: Vehicle[];
  tripId?: string;
  clickedVehicleMarkerId?: number;
  setClickedVehicleMarker: (vehicleId?: number) => void;
};

const Vehicles = memo(function Vehicles({
  vehicles,
  tripId,
  clickedVehicleMarkerId,
  setClickedVehicleMarker,
}: VehiclesProps) {
  const vehiclesById = React.useMemo<{ [id: string]: Vehicle }>(() => {
    return Object.assign({}, ...vehicles.map((item) => ({ [item.id]: item })));
  }, [vehicles]);

  const vehiclesGeoJson = React.useMemo(() => {
    if (vehicles.length < 1000) {
      return null;
    }
    return {
      type: "FeatureCollection",
      features: vehicles
        ? vehicles.map((vehicle) => {
            return {
              type: "Feature",
              id: vehicle.id,
              geometry: {
                type: "Point",
                coordinates: vehicle.coordinates,
              },
              properties: {
                url: vehicle.vehicle?.url,
                colour:
                  vehicle.vehicle?.colour ||
                  (vehicle.vehicle?.css?.length === 7
                    ? vehicle.vehicle.css
                    : "#fff"),
              },
            };
          })
        : [],
    };
  }, [vehicles]);

  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  let markers: ReactElement[] | ReactElement;

  if (!vehiclesGeoJson) {
    markers = vehicles.map((item) => {
      return (
        <VehicleMarker
          key={item.id}
          selected={
            item === clickedVehicle ||
            (tripId && item.trip_id?.toString() === tripId) ||
            false
          }
          vehicle={item}
        />
      );
    });
  } else {
    markers = (
      <Source type="geojson" data={vehiclesGeoJson}>
        <Layer
          {...{
            id: "vehicles",
            type: "circle",
            paint: {
              "circle-color": ["get", "colour"],
            },
          }}
        />
      </Source>
    );
  }

  return (
    <React.Fragment>
      {markers}
      {clickedVehicle && (
        <VehiclePopup
          item={clickedVehicle}
          activeLink={
            tripId ? clickedVehicle.trip_id?.toString() === tripId : false
          }
          onClose={() => setClickedVehicleMarker()}
          snazzyTripLink
        />
      )}
      {clickedVehicle && vehiclesGeoJson && (
        <VehicleMarker selected={true} vehicle={clickedVehicle} />
      )}
    </React.Fragment>
  );
});

function TripSidebar(props: {
  trip?: Trip;
  tripId?: string;
  vehicle?: Vehicle;
  highlightedStop?: string;
}) {
  let className = "trip-timetable map-sidebar";

  const trip = props.trip;

  if (!trip) {
    return <div className={className}></div>;
  }

  if (trip.id && props.tripId !== trip.id?.toString()) {
    className += " loading";
  }

  let operator, service;
  if (trip.operator) {
    operator = (
      <li>
        <a href={`/operators/${trip.operator.slug}`}>{trip.operator.name}</a>
      </li>
    );
  }

  if (props.vehicle?.service) {
    service = (
      <li>
        <a href={props.vehicle.service.url}>
          {props.vehicle.service.line_name}
        </a>
      </li>
    );
  } else if (trip.service?.slug) {
    service = (
      <li>
        <a href={`/services/${trip.service.slug}`}>{trip.service.line_name}</a>
      </li>
    );
  }

  return (
    <div className={className}>
      {operator || service ? (
        <ul className="breadcrumb">
          {operator}
          {service}
        </ul>
      ) : null}
      <TripTimetable
        trip={trip}
        vehicle={props.vehicle}
        highlightedStop={props.highlightedStop}
      />
    </div>
  );
}

function JourneySidebar(props: {
  journey?: Journey;
  journeyId: string;
  vehicle?: Vehicle;
  highlightedStop?: string;
}) {
  let className = "trip-timetable map-sidebar";

  const journey = props.journey;

  if (!journey) {
    return <div className={className}></div>;
  }

  if (journey.id && props.journeyId !== journey.id?.toString()) {
    className += " loading";
  }

  return (
    <div className={className}>
      <p>
        {journey.route_name} to {journey.destination}
      </p>
      <p>
        <a href={`/vehicles/${journey.vehicle.slug}`}>
          {journey.vehicle.fleet_code}{" "}
          <span className="reg">{journey.vehicle.reg}</span>
        </a>
      </p>
      <code>{journey.time_aware_polyline}</code>
    </div>
  );
}

export default function BigMap(
  props: {
    noc?: string;
    trip?: Trip;
    tripId?: string;
    vehicleId?: number;
    journeyId?: string;
  } & (
    | {
        mode: MapMode.Journey;
        journeyId: string;
      }
    | {
        mode: MapMode.Trip | MapMode.Operator | MapMode.Slippy;
      }
  ),
) {
  const mapRef = React.useRef<Map>();

  const [trip, setTrip] = React.useState<Trip | undefined>(props.trip);

  const [journey, setJourney] = React.useState<Journey>();

  const [vehicles, setVehicles] = React.useState<Vehicle[]>();

  const [stops, setStops] = React.useState();

  const [zoom, setZoom] = React.useState<number>();

  const [clickedStopUrl, setClickedStopURL] = React.useState(() => {
    if (document.referrer) {
      const referrer = new URL(document.referrer).pathname;
      if (referrer.indexOf("/stops/") === 0) {
        return referrer;
      }
    }
  });

  const [tripVehicle, setTripVehicle] = React.useState<Vehicle>();

  const initialViewState = useRef(window.INITIAL_VIEW_STATE);

  const tripBounds = React.useMemo(
    function () {
      const times = trip?.times || journey?.times;
      const bounds = new LngLatBounds();
      if (times && times.length) {
        for (const item of times) {
          if (item.stop.location) {
            bounds.extend(item.stop.location);
          }
        }
      } else if (journey?.time_aware_polyline) {
        let lng, lat;
        for ([lat, lng, ] of decodeTimeAwarePolyline(journey.time_aware_polyline)) {
          bounds.extend([lng, lat]);
        }
      }
      if (!bounds.isEmpty()) {
        initialViewState.current = {bounds};
        return bounds;
      }
    },
    [trip, journey],
  );

  React.useEffect(() => {
    if (mapRef.current && tripBounds) {
      mapRef.current.fitBounds(tripBounds, {
        padding: 50,
      });
    }
  }, [tripBounds]);

  const timeout = React.useRef<number>();
  const boundsRef = React.useRef<LngLatBounds>();
  const stopsHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesAbortController = React.useRef<AbortController>();
  const vehiclesLength = React.useRef<number>(0);

  const loadStops = React.useCallback(() => {
    const _bounds = boundsRef.current as LngLatBounds;
    setLoadingStops(true);
    fetchJson("stops.json" + getBoundsQueryString(_bounds)).then((items) => {
      stopsHighWaterMark.current = _bounds;
      setLoadingStops(false);
      setStops(items);
    });
  }, []);

  const [loadingStops, setLoadingStops] = React.useState(false);
  const [loadingBuses, setLoadingBuses] = React.useState(true);

  const loadVehicles = React.useCallback(
    (first = false) => {
      if (!first && document.hidden) {
        return;
      }
      clearTimeout(timeout.current);

      if (vehiclesAbortController.current) {
        vehiclesAbortController.current.abort();
      }
      vehiclesAbortController.current =
        new AbortController() as AbortController;

      let _bounds: LngLatBounds;
      let url: string;
      if (props.mode === MapMode.Slippy) {
        _bounds = boundsRef.current as LngLatBounds;
        if (!_bounds) {
          return;
        }
        url = getBoundsQueryString(_bounds);
      } else if (props.noc) {
        url = "?operator=" + props.noc;
      } else if (trip?.service?.id) {
        url = "?service=" + trip.service.id + "&trip=" + trip.id;
      } else if (props.vehicleId) {
        url = "?id=" + props.vehicleId;
      } else {
        return;
      }

      setLoadingBuses(true);

      return fetch(apiRoot + "vehicles.json" + url, {
        signal: vehiclesAbortController.current.signal,
      })
        .then(
          (response) => {
            if (response.ok) {
              response.json().then((items: Vehicle[]) => {
                vehiclesHighWaterMark.current = _bounds;

                if (first && !initialViewState.current) {
                  const bounds = new LngLatBounds();
                  for (const item of items) {
                    bounds.extend(item.coordinates);
                  }
                  if (!bounds.isEmpty()) {
                    initialViewState.current = {
                      bounds: bounds as LngLatBounds,
                      fitBoundsOptions: {
                        padding: { top: 50, bottom: 150, left: 50, right: 50 },
                      },
                    };
                  }
                }

                if (trip && trip.id) {
                  for (const item of items) {
                    if (trip.id === item.trip_id) {
                      if (first) setClickedVehicleMarker(item.id);
                      setTripVehicle(item);
                      break;
                    }
                  }
                }

                vehiclesLength.current = items.length;
                setVehicles(items);
              });
              setLoadingBuses(false);
            }

            if (!document.hidden) {
              timeout.current = window.setTimeout(loadVehicles, 12000); // 12 seconds
            }
          },
          () => {
            // never mind
            // setLoadingBuses(false);
          },
        )
        .catch(() => {
          // never mind
          // setLoadingBuses(false);
        });
    },
    [props.mode, props.noc, trip, props.vehicleId],
  );

  React.useEffect(() => {
    // trip mode:
    if (props.tripId) {
      if (trip?.id?.toString() === props.tripId) {
        loadVehicles(true);
        document.title = `${trip.service?.line_name} \u2013 ${trip.operator?.name} \u2013 bustimes.org`;
      } else {
        fetch(`${apiRoot}api/trips/${props.tripId}/`).then((response) => {
          if (response.ok) {
            response.json().then(setTrip);
          }
        });
      }
      // operator mode:
    } else if (props.noc) {
      if (props.noc === trip?.operator?.noc) {
        document.title =
          "Bus tracker map \u2013 " +
          trip.operator.name +
          " \u2013 bustimes.org";
      }
      loadVehicles(true);
    } else if (props.journeyId) {
      fetch(`${apiRoot}api/vehiclejourneys/${props.journeyId}/`).then(
        (response) => {
          if (response.ok) {
            response.json().then(setJourney);
          }
        },
      );
    } else if (!props.vehicleId) {
      document.title = "Map \u2013 bustimes.org";
    } else {
      loadVehicles();
    }
  }, [
    props.tripId,
    trip,
    props.noc,
    props.vehicleId,
    props.journeyId,
    loadVehicles,
  ]);

  const handleMoveEnd = debounce(
    React.useCallback(
      (evt: ViewStateChangeEvent) => {
        const map = evt.target;
        boundsRef.current = map.getBounds() as LngLatBounds;
        const zoom = map.getZoom() as number;

        if (shouldShowVehicles(zoom)) {
          if (
            !containsBounds(vehiclesHighWaterMark.current, boundsRef.current) ||
            vehiclesLength.current >= 1000
          ) {
            loadVehicles();
          }

          if (
            shouldShowStops(zoom) &&
            !containsBounds(stopsHighWaterMark.current, boundsRef.current)
          ) {
            loadStops();
          }
        }

        setZoom(zoom);
        updateLocalStorage(zoom, map.getCenter());
      },
      [loadStops, loadVehicles],
    ),
    400,
    { leading: true },
  );

  React.useEffect(() => {
    const handleVisibilityChange = () => {
      if (
        !document.hidden &&
        (props.mode !== MapMode.Slippy || (zoom && shouldShowVehicles(zoom)))
      ) {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [zoom, loadVehicles, props.mode]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] = React.useState<
    number | undefined
  >(props.vehicleId);

  const handleMapClick = React.useCallback(
    (e: MapLayerMouseEvent) => {
      // handle click on VehicleMarker element
      const vehicleId = getClickedVehicleMarkerId(e);
      if (vehicleId) {
        setClickedVehicleMarker(vehicleId);
        setClickedStopURL(undefined);
        return;
      }

      // handle click on maplibre rendered feature
      if (e.features?.length) {
        for (const feature of e.features) {
          if (feature.layer.id === "vehicles" && feature.id) {
            setClickedVehicleMarker(feature.id as number);
            return;
          }
          if (feature.properties.url !== clickedStopUrl) {
            setClickedStopURL(feature.properties.url);
            break;
          }
        }
      } else {
        setClickedStopURL(undefined);
      }
      setClickedVehicleMarker(undefined);
    },
    [clickedStopUrl],
  );

  const handleMapInit = function (map: Map) {
    mapRef.current = map;

    if (props.mode === MapMode.Slippy) {
      const bounds = map.getBounds();
      const zoom = map.getZoom();

      if (!boundsRef.current) {
        // first load
        boundsRef.current = bounds;

        if (shouldShowVehicles(zoom)) {
          loadVehicles();

          if (shouldShowStops(zoom)) {
            loadStops();
          }
        } else {
          boundsRef.current = bounds;
        }
      }
      setZoom(zoom);
    }
  };

  const [cursor, setCursor] = React.useState("");

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor("");
  }, []);

  const showStops = shouldShowStops(zoom);
  const showBuses = props.mode != MapMode.Slippy || shouldShowVehicles(zoom);

  if (props.mode === MapMode.Operator) {
    if (!vehicles) {
      return <div className="sorry">Loading…</div>;
    }
    if (!vehiclesLength.current) {
      return (
        <div className="sorry">Sorry, no buses are tracking at the moment</div>
      );
    }
  }

  if (props.mode === MapMode.Journey && !tripBounds) {
    return <div className="sorry">Loading…</div>;
  }

  let className = "big-map";
  if (props.mode === MapMode.Trip || props.mode === MapMode.Journey) {
    className += " has-sidebar";
  }

  return (
    <React.Fragment>
      {props.mode !== MapMode.Slippy && (
        <Link className="map-link" href="/map">
          Map
        </Link>
      )}
      <div className={className}>
        <BusTimesMap
          initialViewState={initialViewState.current}
          onMoveEnd={props.mode === MapMode.Slippy ? handleMoveEnd : undefined}
          hash={props.mode === MapMode.Slippy}
          onClick={handleMapClick}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          cursor={cursor}
          onMapInit={handleMapInit}
          interactiveLayerIds={["stops", "vehicles"]}
        >
          {props.mode === MapMode.Trip && trip ? (
            <Route times={trip.times} />
          ) : null}

          {props.mode === MapMode.Journey && journey ? (
            <Route times={journey.times} />
          ) : null}

          {props.mode === MapMode.Slippy ? <SlippyMapHash /> : null}

          {trip || journey || (stops && showStops) ? (
            <Stops
              stops={props.mode === MapMode.Slippy ? stops : undefined}
              times={
                props.mode === MapMode.Trip
                  ? trip?.times
                  : props.mode === MapMode.Journey
                    ? journey?.times
                    : undefined
              }
              setClickedStop={setClickedStopURL}
              clickedStopUrl={clickedStopUrl}
            />
          ) : null}

          {vehicles && showBuses ? (
            <Vehicles
              vehicles={vehicles}
              tripId={props.tripId}
              clickedVehicleMarkerId={clickedVehicleMarkerId}
              setClickedVehicleMarker={setClickedVehicleMarker}
            />
          ) : null}

          {zoom &&
          ((props.mode === MapMode.Slippy && !showStops) ||
            loadingBuses ||
            loadingStops) ? (
            <div className="maplibregl-ctrl map-status-bar">
              {props.mode === MapMode.Slippy && !showStops
                ? "Zoom in to see stops"
                : null}
              {!showBuses ? <div>Zoom in to see buses</div> : null}
              {showBuses && (loadingBuses || loadingStops) ? (
                <div>Loading…</div>
              ) : null}
            </div>
          ) : null}
        </BusTimesMap>
      </div>

      {props.mode === MapMode.Trip ? (
        <TripSidebar
          trip={trip}
          tripId={props.tripId}
          vehicle={tripVehicle}
          highlightedStop={clickedStopUrl}
        />
      ) : null}

      {props.mode === MapMode.Journey ? (
        <JourneySidebar
          journey={journey}
          journeyId={props.journeyId}
          highlightedStop={clickedStopUrl}
        />
      ) : null}
    </React.Fragment>
  );
}
