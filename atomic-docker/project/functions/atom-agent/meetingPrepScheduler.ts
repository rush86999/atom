import { agenda } from '../agendaService';
import { listUpcomingEvents } from './skills/calendarSkills';
import { handleMeetingPrep } from './skills/meetingPrep';

agenda.define('generate meeting briefings', async (job) => {
    const { userId } = job.attrs.data;

    const events = await listUpcomingEvents(userId, 10);

    for (const event of events) {
        await handleMeetingPrep(userId, {
            meeting_title: event.summary,
            attendees: event.attendees,
        });
    }
});

(async function() {
    await agenda.start();
    await agenda.every('0 9 * * *', 'generate meeting briefings', { userId: 'mock_user_id_from_handler' });
})();
