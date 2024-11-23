import React, { type ReactElement, memo, useEffect, useRef } from "react";

import { Hash, type LngLatBounds, type Map as MapGL } from "maplibre-gl";
import {
  Layer,
  type MapLayerMouseEvent,
  type MapProps,
  Source,
  type ViewStateChangeEvent,
  useMap,
} from "react-map-gl/maplibre";
import { Link } from "wouter";

import debounce from "lodash/debounce";

import VehicleMarker, {
  type Vehicle as VehicleLocation,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";

import { JourneyStops, Locations, type VehicleJourney } from "./JourneyMap";
import LoadingSorry from "./LoadingSorry";
import BusTimesMap from "./Map";
import StopPopup, { type Stop } from "./StopPopup";
import { Route } from "./TripMap";
import TripTimetable, { type Trip, tripFromJourney } from "./TripTimetable";
import VehiclePopup from "./VehiclePopup";
import { getBounds } from "./utils";

import { decodeTimeAwarePolyline } from "./time-aware-polyline";

const apiRoot = process.env.API_ROOT;

declare global {
  interface Window {
    INITIAL_VIEW_STATE: MapProps["initialViewState"];
  }
}

const updateLocalStorage = debounce((zoom: number, latLng) => {
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
  // console.log(a, b);
  // if (a) {
  //   console.log("N", a.getNorth(), b.getNorth(), a.getNorth() >= b.getNorth());
  //   console.log("E ", a.getEast(), b.getEast(), a.getEast() >= b.getEast());
  //   console.log("S ", a.getSouth(), b.getSouth(), a.getSouth() <= b.getSouth());
  //   console.log("W ", a.getWest(), b.getWest(), a.getWest() <= b.getWest());
  // }

  // console.log(a?.contains(b.getNorthWest()) && a.contains(b.getSouthEast()));
  return a?.contains(b.getNorthWest()) && a.contains(b.getSouthEast());
}

function shouldShowStops(zoom?: number) {
  return zoom && zoom >= 14;
}

function shouldShowVehicles(zoom?: number) {
  return zoom && zoom >= 6;
}

export enum MapMode {
  Slippy = 0,
  Operator = 1,
  Trip = 2,
  Journey = 3,
}

type Journey = {
  id: number;
  datetime: string | number;
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
  service: {
    id: number;
    slug: string;
  };
};

function SlippyMapHash() {
  const mapRef = useMap();

  React.useEffect(() => {
    if (mapRef.current) {
      const map = mapRef.current.getMap();
      const hash = map._hash || new Hash();
      map._hash = hash;
      hash.addTo(map);
      return () => {
        hash.remove();
      };
    }
  }, [mapRef]);

  return null;
}

function Stops({
  stops,
  times,
  clickedStopUrl,
  setClickedStop,
}: {
  stops?: {
    features: Stop[];
  };
  times?: Trip["times"];
  clickedStopUrl?: string;
  setClickedStop: (stop?: string) => void;
}) {
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
          const url = `/stops/${time.stop.atco_code}`;
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
  vehicles: VehicleLocation[];
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
  const vehiclesById = React.useMemo<{ [id: string]: VehicleLocation }>(() => {
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
  vehicle?: VehicleLocation;
  highlightedStop?: string;
}) {
  let className = "trip-timetable map-sidebar";

  const trip = props.trip;

  if (!trip) {
    return <div className={className} />;
  }

  if (trip.id && props.tripId !== trip.id?.toString()) {
    className += " loading";
  }

  const operator = trip.operator ? (
    <li>
      <a href={`/operators/${trip.operator.slug}`}>{trip.operator.name}</a>
    </li>
  ) : null;

  const service = props.vehicle?.service ? (
    <li>
      <a href={props.vehicle.service.url}>{props.vehicle.service.line_name}</a>
    </li>
  ) : trip.service?.slug ? (
    <li>
      <a href={`/services/${trip.service.slug}`}>{trip.service.line_name}</a>
    </li>
  ) : null;

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
  journey: VehicleJourney;
  journeyId: string;
  highlightedStop?: string;
  vehicle?: VehicleLocation;
}) {
  const className = "trip-timetable map-sidebar";

  const journey = props.journey;

  const trip = React.useMemo(() => {
    return tripFromJourney(journey);
  }, [journey]);

  let service: string | ReactElement =
    `${journey.route_name} to ${journey.destination}`;
  if (props.vehicle?.service?.url) {
    service = <a href={props.vehicle.service.url}>{service}</a>;
  }

  // if (!journey) {
  //   return <div className={className}></div>;
  // }

  // if (journey.id && props.journeyId !== journey.id?.toString()) {
  //   className += " loading";
  // }

  return (
    <div className={className}>
      <p>{service}</p>
      {/* {journey.vehicle ? (
        <p>
          <a
            href={`/vehicles/${journey.vehicle.slug}`}
            className="vehicle-link"
          >
            {journey.vehicle.fleet_code}{" "}
            <span className="reg">{journey.vehicle.reg}</span>
          </a>
        </p>
      ) : null} */}
      {trip ? <TripTimetable trip={trip} vehicle={props.vehicle} /> : null}
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
  const mapRef = React.useRef<MapGL>();

  const [trip, setTrip] = React.useState<Trip | undefined>(props.trip);

  const [journey, setJourney] = React.useState<VehicleJourney>();

  const [vehicles, setVehicles] = React.useState<VehicleLocation[]>();

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

  const [tripVehicle, setTripVehicle] = React.useState<VehicleLocation>();

  const initialViewState = useRef(window.INITIAL_VIEW_STATE);

  const fitBounds = React.useCallback((bounds?: LngLatBounds) => {
    if (bounds) {
      if (!initialViewState.current) {
        initialViewState.current = { bounds };
      } else if (mapRef.current) {
        mapRef.current.fitBounds(bounds, {
          padding: 50,
        });
      }
    }
  }, []);

  useEffect(() => {
    const times = trip?.times;
    if (times?.length) {
      fitBounds(getBounds(times, (time) => time.stop.location));
    } else if (journey) {
      fitBounds(getBounds(journey.locations, (item) => item.coordinates));
    }
  }, [trip, journey, fitBounds]);

  const timeout = React.useRef<number>();
  const boundsRef = React.useRef<LngLatBounds>();
  const stopsHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesAbortController = React.useRef<AbortController>();
  const vehiclesLength = React.useRef<number>(0);

  const loadStops = React.useCallback(() => {
    const _bounds = boundsRef.current as LngLatBounds;
    setLoadingStops(true);
    fetchJson(`stops.json${getBoundsQueryString(_bounds)}`).then((items) => {
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
        vehiclesAbortController.current = undefined;
      }

      let _bounds: LngLatBounds;
      let url: string;
      if (props.mode === MapMode.Slippy) {
        _bounds = boundsRef.current as LngLatBounds;
        if (!_bounds) {
          return;
        }
        url = getBoundsQueryString(_bounds);
      } else if (props.noc) {
        url = `?operator=${props.noc}`;
      } else if (trip?.service?.id) {
        url = `?service=${trip.service.id}&trip=${trip.id}`;
      } else if (props.vehicleId) {
        url = `?id=${props.vehicleId}`;
      } else if (journey?.vehicle_id) {
        url = `?id=${journey.vehicle_id}`;
      } else {
        return;
      }

      setLoadingBuses(true);

      vehiclesAbortController.current =
        new AbortController() as AbortController;

      return fetch(`${apiRoot}vehicles.json${url}`, {
        signal: vehiclesAbortController.current.signal,
      })
        .then(
          (response) => {
            if (response.ok) {
              response.json().then((items: VehicleLocation[]) => {
                vehiclesHighWaterMark.current = _bounds;

                if (!initialViewState.current) {
                  const bounds = getBounds(items, (item) => item.coordinates);
                  if (bounds) {
                    initialViewState.current = {
                      bounds,
                      fitBoundsOptions: {
                        padding: { top: 50, bottom: 150, left: 50, right: 50 },
                      },
                    };
                  }
                }

                if (trip || journey?.vehicle_id) {
                  for (const item of items) {
                    if (
                      (trip && trip.id === item.trip_id) ||
                      journey?.vehicle_id === item.id
                    ) {
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
    [props.mode, props.noc, trip, journey?.vehicle_id, props.vehicleId],
  );

  React.useEffect(() => {
    if (props.tripId) {
      // trip mode
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
    } else if (props.noc) {
      // operator mode
      if (props.noc === trip?.operator?.noc) {
        document.title = `Bus tracker map \u2013 ${trip.operator.name} \u2013 bustimes.org`;
      }
      loadVehicles(true);
    } else if (props.journeyId) {
      // journey mode
      if (journey?.id?.toString() === props.journeyId) {
        if (journey.current) {
          loadVehicles(true);
        }
      } else {
        fetch(`${apiRoot}journeys/${props.journeyId}.json`).then((response) => {
          if (response.ok) {
            response.json().then((journey: VehicleJourney) => {
              setJourney({ ...journey, id: props.journeyId });
            });
          }
        });
      }
    } else if (!props.vehicleId) {
      // slippy mode
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
    journey,
    loadVehicles,
  ]);

  const handleMoveEnd = React.useCallback(
    debounce(
      React.useCallback(
        (evt: ViewStateChangeEvent) => {
          const map = evt.target;
          boundsRef.current = map.getBounds() as LngLatBounds;
          const zoom = map.getZoom() as number;

          if (shouldShowVehicles(zoom)) {
            if (
              !containsBounds(
                vehiclesHighWaterMark.current,
                boundsRef.current,
              ) ||
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
    ),
    [],
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

  const handleMapInit = (map: MapGL) => {
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

  const [cursor, setCursor] = React.useState<string>();

  const hoveredLocation = React.useRef<number>();

  const onMouseEnter = React.useCallback((e: MapLayerMouseEvent) => {
    const vehicleId = getClickedVehicleMarkerId(e);
    if (vehicleId) {
      return;
    }

    if (e.features?.length) {
      setCursor("pointer");
      // journey map
      for (const feature of e.features) {
        if (feature.layer.id === "locations") {
          if (hoveredLocation.current !== undefined) {
            e.target.setFeatureState(
              { source: "locations", id: hoveredLocation.current },
              { hover: false },
            );
          }
          e.target.setFeatureState(
            { source: "locations", id: feature.id },
            { hover: true },
          );
          hoveredLocation.current = feature.id as number;
          return;
        }
      }
    }
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(undefined);
  }, []);

  const showStops = shouldShowStops(zoom);
  const showBuses = props.mode !== MapMode.Slippy || shouldShowVehicles(zoom);

  if (props.mode === MapMode.Operator) {
    if (!vehicles) {
      return <LoadingSorry />;
    }
    if (!vehiclesLength.current) {
      return (
        <LoadingSorry
          text={
            <p>
              Sorry, no buses are tracking at the moment.{" "}
              <a href="/map">Go to the main map?</a>
            </p>
          }
        />
      );
    }
  }

  if (props.mode === MapMode.Journey && !initialViewState.current) {
    return <LoadingSorry />;
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
          onMouseMove={
            props.mode === MapMode.Journey ? onMouseEnter : undefined
          }
          onMouseLeave={onMouseLeave}
          cursor={cursor}
          onMapInit={handleMapInit}
          interactiveLayerIds={["stops", "vehicles", "locations"]}
        >
          {props.mode === MapMode.Trip && trip ? (
            <Route times={trip.times} />
          ) : null}

          {props.mode === MapMode.Journey && journey?.stops ? (
            <JourneyStops
              stops={journey.stops}
              clickedStopUrl={clickedStopUrl}
              setClickedStop={setClickedStopURL}
            />
          ) : null}

          {props.mode === MapMode.Slippy ? <SlippyMapHash /> : null}

          {trip || (stops && showStops) ? (
            <Stops
              stops={props.mode === MapMode.Slippy ? stops : undefined}
              times={props.mode === MapMode.Trip ? trip?.times : undefined}
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

          {props.mode === MapMode.Journey && journey && (
            <Locations locations={journey.locations} />
          )}
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

      {props.mode === MapMode.Journey && journey ? (
        <JourneySidebar
          journey={journey}
          journeyId={props.journeyId}
          vehicle={tripVehicle}
          highlightedStop={clickedStopUrl}
        />
      ) : null}
    </React.Fragment>
  );
}
