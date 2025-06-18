CREATE TABLE admin_user (
  id INT,
  username VARCHAR(255),
  password VARCHAR(255),
  role VARCHAR(255)
);

INSERT INTO admin_user (id, username, password, role) VALUES (1, 'admin', 'password', 'admin');

create table event_optaplanner (id varchar(255) not null, hostId uuid, userId uuid, primary key (id));
create table event_part_optaplanner (id int8 not null, dailyTaskList boolean not null, endDate varchar(255), eventId varchar(255), forEventId varchar(255), gap boolean not null, groupId varchar(255), hardDeadline varchar(255), hostId uuid, isExternalMeeting boolean not null, isExternalMeetingModifiable boolean not null, isMeeting boolean not null, isMeetingModifiable boolean not null, isPostEvent boolean not null, isPreEvent boolean not null, lastPart int4 not null, meetingId varchar(255), meetingLastPart int4 not null, meetingPart int4 not null, modifiable boolean not null, negativeImpactDayOfWeek int4, negativeImpactScore int4 not null, negativeImpactTime time, part int4 not null, positiveImpactDayOfWeek int4, positiveImpactScore int4 not null, positiveImpactTime time, preferredDayOfWeek int4, preferredEndTimeRange time, preferredStartTimeRange time, preferredTime time, priority int4 not null, softDeadline varchar(255), startDate varchar(255), taskId varchar(255), totalWorkingHours int4 not null, userId uuid, weeklyTaskList boolean not null, timeslot_id int8, primary key (id));
create table preferredTimeRange_optaplanner (id int8 not null, dayOfWeek int4, endTime time, eventId varchar(255), hostId uuid, startTime time, userId uuid, primary key (id));
create table timeslot_optaplanner (id int8 not null, dayOfWeek int4, endTime time, hostId uuid, monthDay varchar(255), startTime time, primary key (id));
create table user_optaplanner (id uuid not null, backToBackMeetings boolean not null, hostId uuid, maxNumberOfMeetings int4 not null, maxWorkLoadPercent int4 not null, minNumberOfBreaks int4 not null, primary key (id));
create table workTime_optaplanner (id int8 not null, dayOfWeek int4, endTime time, hostId uuid, startTime time, userId uuid, primary key (id));
create index sk_userId_event_optaplanner on event_optaplanner (userId);
create index sk_hostId_event_optaplanner on event_optaplanner (hostId);
create index sk_userId_eventPart_optaplanner on event_part_optaplanner (userId);
create index sk_groupId_eventPart_optaplanner on event_part_optaplanner (groupId);
create index sk_eventId_eventPart_optaplanner on event_part_optaplanner (eventId);
create index sk_hostId_eventPart_optaplanner on event_part_optaplanner (hostId);
create index sk_eventId_preferredTimeRange_optaplanner on preferredTimeRange_optaplanner (eventId);
create index sk_userId_preferredTimeRange_optaplanner on preferredTimeRange_optaplanner (userId);
create index sk_hostId_preferredTimeRange_optaplanner on preferredTimeRange_optaplanner (hostId);
create index sk_timeslot_hostId_optaplanner on timeslot_optaplanner (hostId);
create index sk_hostId_user_optaplanner on user_optaplanner (hostId);
create index sk_userId_workTime_optaplanner on workTime_optaplanner (userId);
create index sk_hostId_workTime_optaplanner on workTime_optaplanner (hostId);
create sequence hibernate_sequence start 1 increment 1;
alter table if exists event_part_optaplanner add constraint FKi0pl5rc8eang05vdsc1274cmb foreign key (eventId) references event_optaplanner;
alter table if exists event_part_optaplanner add constraint FKrc6mx3f0p8evu5cpryix0pswu foreign key (timeslot_id) references timeslot_optaplanner;
alter table if exists event_part_optaplanner add constraint FK1a8wkuvkkrju0bfxo8se32eo3 foreign key (userId) references user_optaplanner;
alter table if exists preferredTimeRange_optaplanner add constraint FKdd37a30iji98r7fy0rur1v6d1 foreign key (eventId) references event_optaplanner;
