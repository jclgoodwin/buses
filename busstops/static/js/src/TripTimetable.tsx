import React, { ReactElement } from "react";
import { Vehicle } from "./VehicleMarker";

export type TripTime = {
  id: number;
  stop: {
    name: string;
    atco_code?: string;
    location?: [number, number];
    icon?: string;
    bearing?: number;
  };
  track?: [number, number][];
  aimed_arrival_time: string;
  aimed_departure_time: string;
  expected_departure_time?: string;
  expected_arrival_time?: string;
  actual_departure_time?: string;
  // actual_arrival_time: string;
  timing_status: string;
};

type Note = {
  code: string;
  text: string;
};

export type Trip = {
  id?: number;
  times: TripTime[];
  notes?: Note[];
};

type RowProps = {
  stop: TripTime;
  onMouseEnter: (stop: TripTime) => void;
  vehicle: any;
  aimedColumn?: boolean;
};

function Row({ stop, onMouseEnter, vehicle, aimedColumn }: RowProps) {
  const handleMouseEnter = React.useCallback(() => {
    if (onMouseEnter) {
      if (stop.stop.location) {
        onMouseEnter(stop);
      }
    }
  }, [stop, onMouseEnter]);

  let stopName: any = stop.stop.name;
  if (stop.stop.icon) {
    stopName = `${stopName} (${stop.stop.icon})`;
  }
  if (stop.stop.atco_code) {
    stopName = <a href={`/stops/${stop.stop.atco_code}`}>{stopName}</a>;
  }

  const className = stop.timing_status === "OTH" ? "minor" : null;

  const rowSpan =
    aimedColumn &&
    stop.aimed_arrival_time &&
    stop.aimed_departure_time &&
    stop.aimed_arrival_time !== stop.aimed_departure_time
      ? 2
      : null;

  let actual;
  if (vehicle?.progress && vehicle.progress.prev_stop === stop.stop.atco_code) {
    actual = vehicle.datetime;
  } else {
    actual = stop.actual_departure_time;
  }
  if (actual) {
    actual = new Date(actual).toTimeString().slice(0, 8);
  } else {
    actual = stop.expected_departure_time || stop.expected_arrival_time;
  }
  if (actual) {
    actual = <td>{actual}</td>;
  }

  return (
    <React.Fragment>
      <tr className={className} onMouseEnter={handleMouseEnter}>
        <td className="stop-name" rowSpan={rowSpan}>
          {stopName}
        </td>
        {aimedColumn ? (
          <td>{stop.aimed_arrival_time || stop.aimed_departure_time}</td>
        ) : null}
        {actual}
      </tr>
      {rowSpan ? (
        <tr className={className}>
          <td>{stop.aimed_departure_time}</td>
        </tr>
      ) : null}
    </React.Fragment>
  );
}

type TripTimetableProps = {
  trip: Trip;
  onMouseEnter?: (stop: TripTime) => void;
  vehicle?: Vehicle;
  loading?: boolean | null;
};

const TripTimetable = React.memo(function TripTimetable({
  trip,
  onMouseEnter,
  vehicle,
}: TripTimetableProps) {
  // const last = trip.times?.length - 1;

  const aimedColumn = trip.times?.some(
    (item: TripTime) => item.aimed_arrival_time || item.aimed_departure_time,
  );

  return (
    <React.Fragment>
      <table>
        <thead>
          <tr>
            <th></th>
            {aimedColumn ? <th>Timetable</th> : null}
            <th>Actual</th>
          </tr>
        </thead>
        <tbody>
          {trip.times.map((stop, i) => (
            <Row
              key={stop.id || i}
              aimedColumn={aimedColumn}
              stop={stop}
              onMouseEnter={onMouseEnter}
              vehicle={vehicle}
            />
          ))}
        </tbody>
      </table>
      {trip.notes?.map((note) => <p key={note.code}>{note.text}</p>)}
    </React.Fragment>
  );
});

export default TripTimetable;
