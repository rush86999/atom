<h1 align="center">Atomic - An open-source priority-driven AI scheduler to solve your time problems</h1>

<h2 align="center">An alternative to Motion, Clockwise, Cal.ai & Reclaim</h2>

⭐⭐⭐ If you like where this repo is heading, please support me with a star on the top right corner ⭐⭐⭐

⭐⭐⭐ Self-hosted now available :) ⭐⭐⭐

For a good user experience use [Groq](https://wow.groq.com/)


https://github.com/rush86999/atomic/assets/16848240/da8c0826-573e-44a4-849b-083d61dc4c60

https://github.com/rush86999/atomic/assets/16848240/b2dc08e8-8e9f-41b5-b249-dadb13b914c6

https://github.com/rush86999/atomic/assets/16848240/9390a703-31fa-4622-b6be-818bf462b3f8

https://github.com/rush86999/atomic/assets/16848240/5720e9a3-e4d6-4dce-8e3c-5d614a39e305


## Table of Contents
- [Table of Contents](#table-of-contents)
- [Problem](#problem)
- [Documentation](#documentation)
- [Features](#features)
    - [Benefits of Self Hosted](#benefits-of-self-hosted)
  - [Cloud Hosted Atomic](#cloud-hosted-atomic)
  - [Customize Atomic for your team on your cloud](#customize-atomic-for-your-team-on-your-cloud)
- [Diagram](#diagram)
  - [Meeting Assist](#meeting-assist)
- [Docker](#docker)
- [Support the Project](#support-the-project)
- [Contributing](#contributing)


## Problem
Scheduling and managing time is always a problem. Finding a time that works for everybody is a bigger problem. What if you can tell your calendar your time preferences and priorities for things you have to do every day? Now what if everyone on your team could do the same thing? Now finding a time becomes easier when everyone's priorities are accounted for. 

Let all of this happen automatically for you and your team on a daily basis before work starts.

All of this is possible with vector-based search to create a memory for your calendar and Autopilot.

Memory + Decisions + Natural Conversation Interface => Perfect Time Management Assistant

It will be easier than ever to teach, find, block, create, meet, schedule, update, and more with your calendar using ChatGPT. The goal is to allow a natural conversation with your calendar assistant for your end goals.

Examples:

1. "Schedule a meeting with [person] at [date and time] for [purpose]."
2. "Remind me to follow up with [person] on [date] regarding [topic]."
3. "Block off [time frame] for [task or activity]."
4. "Find an available time slot for a team meeting with [list of attendees]."
5. "Let's respond to emails either on 8 - 11 am or 2 - 4 pm on weekdays with a priority of 3"
6. "Let's have [X] meetings on either Mondays or Wednesdays, anytime between 8 - 11 am, and keep it a priority of 5"
7. "When is my next appointment?"
8. "What time is my meeting with [person] on [date]?"
9. "Are there any overlapping events on my calendar?"
10. "Do I have any free time on Thursday?"


For simple 1:1 meetings, you won't need calendly links anymore. Your recipient replies to you and Atomic, and a meeting gets scheduled for you automatically.

## Documentation

- You can find documentation on how to use Atomic at https://docs.atomiclife.app

## Features

| Feature | Description |
| ----------- | ----------- |
| Semantic search | Use unique key phrases to match semantically similar past task events and apply them to new ones. Now your past tasks are templates for new ones! Apply duration, color, time preferences, priority, tags and more. Event details are converted into vectors and indexed for search. The vectorization of event details now leverages direct calls to advanced OpenAI embedding models for enhanced performance and cost-effectiveness. Note: You need to "train" Atomic on existing events to create event templates for new events. Read the [docs](https://docs.atomiclife.app) for more info. |
| Automated tagging | Apply tags automatically using an AI model used for classification. Each tag comes with its own set of settings configured to apply to all matched events. This classification is now primarily handled by direct integration with powerful OpenAI language models. |
| Flexible Meetings | Create recurring 1:1's or ad hoc team meetings that works with everyone's schedule. Every attendee's calendar is taken into account. Non-Atomic users can also sync their calendars and submit their time preferences. Once setup, your flexible recurring meetings occur automagically conflict free based on your time preferences.|
| Autopilot | You can run the AI planner on Autopilot that will also search & apply features to new events based on past trained event templates. The AI planner will always run before your work day starts |
|Time Preferences |Select time preferences for flexible meetings and other modifiable events |
| Train events| You can train existing events and make them templates for new ones. Attributes you can change include transparency, buffer times, priority, time preferences, modifiable nature, tags, color, duration, break type, alarms. You can also "untrain" by turning "link off" in the event menu options.|
| Time Blocking | You can automate time blockings of tasks that have a daily or weekly deadline with priority to let Atomic place them in the right place on your calendar. The deadlines can be soft or hard based on your requirements.|
|Priority | You can set priority to modifiable events. Priority of 1 is neutral. 1 has no impact on the AI planner's decision making process. Any number > 1 will impact sooner it appears on the calendar relative other low priority events.|
|Rating| You can rate events to tell Atomic how productive you were for the time block. Next run, Atomic will take it into consideration before the placing the event if it's modifiable|
| Smart Tags | You can apply settings to tags. These settings will tell Atomic how to apply features or attributes to new events that are tagged by the AI model or manually.|

#### Benefits of Self Hosted
- Privacy enabled by default
- Customizable - adjust any parameters to make it work to your requirements

### Cloud Hosted Atomic
- Prioritized version
- Full customer support & bug fixes
- Road map
  - SSO for teams
  - Microsoft Outlook Calendar integration
  - ChatGPT integration for Premium version
  - Zoom video is integrated.
  - docker self-hosted version

### Customize Atomic for your team on your cloud
- Same level of support & features as cloud hosted version
- Same features
- 1 year support included
- $15 / month support afterwards
## Diagram

### Meeting Assist
```mermaid
    sequenceDiagram
    actor Alice
    participant A as Atomic
    actor Bob
    actor John
    participant H as handshake.atomiclife.app
    participant P as AI Scheduler

    participant G as Google Calendar
    Alice->>A: Create a new meeting assist with John & Bob as attendees
    A->>John: Sends handshake link for a possible meeting
    A->>Bob: Sends another handshake link to another attendee 
    John->>H: Selects time preferences (not availability like a booking link)
    Bob->>H: Also selects time preferences
    H->>P: Submits & starts AI planner after minimum threshold met
    P->>G: finds an optimal slot & creates the new event

```

## Docker
- Self hosted docker compose
- See [atomic-docker](./atomic-docker/README.md) branch for more details

## Support the Project
- I'm spending 100% of my work time on this project
- Star this repository, so I can start an Open Collective to support this project
- In process of setting up Github Sponsors
- Follow me on Twitter: https://twitter.com/rish1_2
- Used Atomic? write a review or let me know!

## Contributing

1. Fork this repository and clone the fork to your machine
2. Create a branch (`git checkout -b my-new-feature`)
3. Implement a new feature or fix a bug and add some tests or proof of fix
4. Commit your changes (`git commit -am 'Added a new feature'`)
5. Push the branch to your fork on GitHub (`git push origin my-new-feature`)
6. Create new Pull Request from your fork

