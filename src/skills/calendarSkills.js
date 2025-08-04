"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.findCalendarEventByFuzzyReference = findCalendarEventByFuzzyReference;
const STOP_WORDS = [
    'a',
    'an',
    'and',
    'are',
    'as',
    'at',
    'be',
    'but',
    'by',
    'for',
    'if',
    'in',
    'into',
    'is',
    'it',
    'its',
    'my',
    'no',
    'not',
    'of',
    'on',
    'or',
    'such',
    'that',
    'the',
    'their',
    'then',
    'there',
    'these',
    'they',
    'this',
    'to',
    'was',
    'will',
    'with',
    'i',
    'me',
    'you',
    'he',
    'she',
    'we',
    'us',
    'am',
    'pm', // also time indicators if not handled by date parser
];
/**
 * Generates n-grams (specifically bigrams) from a string.
 * @param str The input string.
 * @param n The size of the n-grams (default is 2 for bigrams).
 * @returns An array of n-grams.
 */
function _getNgrams(str, n = 2) {
    const cleanedStr = str.toLowerCase().replace(/[^a-z0-9]/g, ''); // Keep only alphanumeric for n-grams
    if (cleanedStr.length < n) {
        return [];
    }
    const ngrams = [];
    for (let i = 0; i <= cleanedStr.length - n; i++) {
        ngrams.push(cleanedStr.substring(i, i + n));
    }
    return ngrams;
}
/**
 * Calculates string similarity based on n-gram comparison (Sørensen-Dice coefficient).
 * @param str1 First string.
 * @param str2 Second string.
 * @param n N-gram size (default 2 for bigrams).
 * @returns Similarity score between 0 and 1.
 */
function getStringSimilarity(str1, str2, n = 2) {
    if (!str1 || !str2) {
        return 0;
    }
    // Normalize strings for comparison beyond just n-gram generation (e.g. full string if short)
    const s1 = str1.toLowerCase().replace(/\s+/g, '');
    const s2 = str2.toLowerCase().replace(/\s+/g, '');
    if (s1 === s2) {
        // Exact match after normalization
        return 1.0;
    }
    const ngrams1 = _getNgrams(s1, n);
    const ngrams2 = _getNgrams(s2, n);
    if (ngrams1.length === 0 || ngrams2.length === 0) {
        return 0;
    }
    const set1 = new Set(ngrams1);
    const set2 = new Set(ngrams2);
    let commonCount = 0;
    for (const ngram of set1) {
        if (set2.has(ngram)) {
            // For actual Dice, you'd count occurrences in lists, not just presence in sets,
            // if strings can have repeated n-grams. For simplicity with sets:
            commonCount++;
        }
    }
    // Simplified Dice for sets: (2 * |Intersection|) / (|Set1| + |Set2|)
    // More accurate Dice for bags (multisets) of ngrams: (2 * commonNgramsCount) / (ngrams1.length + ngrams2.length)
    // Let's do the more accurate one by iterating through one list and removing from a copy of the other.
    commonCount = 0;
    const ngrams2Copy = [...ngrams2];
    for (const ngram of ngrams1) {
        const indexInCopy = ngrams2Copy.indexOf(ngram);
        if (indexInCopy !== -1) {
            commonCount++;
            ngrams2Copy.splice(indexInCopy, 1); // Remove to handle duplicates correctly
        }
    }
    return (2 * commonCount) / (ngrams1.length + ngrams2.length);
}
/**
 * Extracts a display name from a typical calendar attendee string.
 * @param attendeeString The raw attendee string (e.g., "John Doe <john.doe@example.com>", "jane@example.com").
 * @returns A lowercase, cleaned name part or an empty string.
 */
function _extractNameFromAttendeeString(attendeeString) {
    if (!attendeeString)
        return '';
    attendeeString = attendeeString.toLowerCase();
    // Case 1: "FullName <email>" or "FirstName <email>"
    const emailMatch = attendeeString.match(/^(.*?)<.*>$/);
    if (emailMatch && emailMatch[1]) {
        return emailMatch[1].trim();
    }
    // Case 2: "Name (Guest)" or "Name (External)"
    const guestMatch = attendeeString.match(/^(.*?)\s*\((guest|external)\)/);
    if (guestMatch && guestMatch[1]) {
        return guestMatch[1].trim();
    }
    // Case 3: Just an email "user@example.com" -> "user"
    if (attendeeString.includes('@')) {
        const parts = attendeeString.split('@');
        // Further clean username part if it contains dots or numbers that are not part of typical first/last names
        // For simplicity here, just taking the part before @. More sophisticated cleaning could be added.
        return parts[0].replace(/[^a-z\s'-]/gi, '').trim(); // Keep letters, spaces, hyphens, apostrophes
    }
    // Case 4: Just a name (no email, no guest marker)
    // Clean it similarly to the email username part
    return attendeeString.replace(/[^a-z\s'-]/gi, '').trim();
}
/**
 * Finds a calendar event based on a natural language reference and optional date hints.
 *
 * @param userId The ID of the user whose calendar is to be searched.
 * @param meeting_reference A natural language string describing the meeting
 *                          (e.g., "my sync up tomorrow", "budget review next week").
 * @param date_hints Optional hints to narrow down the date range for the search.
 * @returns A Promise that resolves to a CalendarEventSummary if a suitable event
 *          is found, or undefined otherwise.
 */
async function findCalendarEventByFuzzyReference(userId, meeting_reference, date_hints) {
    console.log(`[findCalendarEventByFuzzyReference] Inputs: userId=${userId}, reference="${meeting_reference}", hints=${JSON.stringify(date_hints)}`);
    // 1. Determine search window based on date_hints or defaults.
    let searchWindowStart;
    let searchWindowEnd;
    const now = new Date();
    if (date_hints?.specificDate) {
        searchWindowStart = new Date(date_hints.specificDate);
        searchWindowStart.setHours(0, 0, 0, 0); // Start of the day
        searchWindowEnd = new Date(date_hints.specificDate);
        searchWindowEnd.setHours(23, 59, 59, 999); // End of the day
    }
    else if (date_hints?.startDate && date_hints?.endDate) {
        searchWindowStart = new Date(date_hints.startDate);
        searchWindowEnd = new Date(date_hints.endDate);
    }
    else if (date_hints?.startDate) {
        searchWindowStart = new Date(date_hints.startDate);
        searchWindowEnd = new Date(searchWindowStart);
        searchWindowEnd.setDate(searchWindowStart.getDate() + 14); // Default 2 weeks window
        searchWindowEnd.setHours(23, 59, 59, 999);
    }
    else if (date_hints?.endDate) {
        searchWindowEnd = new Date(date_hints.endDate);
        searchWindowStart = new Date(searchWindowEnd);
        searchWindowStart.setDate(searchWindowEnd.getDate() - 14); // Default 2 weeks window prior
        searchWindowStart.setHours(0, 0, 0, 0);
    }
    else {
        // Default search window: from start of today to 14 days in the future
        searchWindowStart = new Date(now);
        searchWindowStart.setHours(0, 0, 0, 0);
        searchWindowEnd = new Date(now);
        searchWindowEnd.setDate(now.getDate() + 14);
        searchWindowEnd.setHours(23, 59, 59, 999);
    }
    console.log(`[findCalendarEventByFuzzyReference] Determined search window: ${searchWindowStart.toISOString()} to ${searchWindowEnd.toISOString()}`);
    // 2. Fetch calendar events for the user within that window (mocked for now).
    const mockEvents = await mockFetchUserCalendarEvents(userId, searchWindowStart, searchWindowEnd);
    console.log(`[findCalendarEventByFuzzyReference] Fetched ${mockEvents.length} mock events.`);
    // 3. Apply matching logic (fuzzy, keyword, or LLM-based) against meeting_reference.
    if (mockEvents.length === 0) {
        console.log('[findCalendarEventByFuzzyReference] No mock events found in the search window. Returning undefined.');
        return undefined;
    }
    const meetingReferenceLower = meeting_reference.toLowerCase();
    // Enhanced keyword extraction:
    // 1. Split by non-alphanumeric characters (handles punctuation better than just space)
    // 2. Filter out stop words
    // 3. Filter out very short words (e.g., < 3 chars)
    const rawWords = meetingReferenceLower.split(/[^a-z0-9]+/).filter(Boolean); // Split and remove empty strings
    const keywords = rawWords.filter((word) => !STOP_WORDS.includes(word) && word.length >= 3);
    if (keywords.length === 0 && rawWords.length > 0) {
        // If all words were stop words or too short, fall back to using all short words from original reference
        // to catch cases like "1:1" or if the meeting title itself is very short and like a stop word.
        console.log('[findCalendarEventByFuzzyReference] No significant keywords after filtering, falling back to raw short words if any.');
        keywords.push(...rawWords.filter((word) => word.length > 0 && word.length < 3)); // Add back very short words
        if (keywords.length === 0) {
            // If still nothing, use all raw words
            keywords.push(...rawWords);
        }
        console.log(`[findCalendarEventByFuzzyReference] Fallback keywords: ${keywords.join(', ')}`);
    }
    console.log(`[findCalendarEventByFuzzyReference] Processed Keywords from reference: ${keywords.join(', ')}`);
    const processedReference = keywords.join(' '); // Use this for overall similarity
    let bestMatch = undefined;
    let highestScore = 0.0; // Scores are now float (0.0 to 1.0+)
    for (const event of mockEvents) {
        const eventTitleLower = event.title.toLowerCase();
        const eventDescriptionLower = event.description?.toLowerCase() || '';
        // Primary score from fuzzy matching the processed reference against the event title
        let currentScore = getStringSimilarity(processedReference, eventTitleLower);
        // console.log(`[findCalendarEventByFuzzyReference] Event: "${event.title}", Initial Similarity Score: ${currentScore.toFixed(3)}`);
        // Bonus for exact keyword matches in title
        let titleBonus = 0;
        for (const keyword of keywords) {
            if (eventTitleLower.includes(keyword)) {
                titleBonus += 0.05; // Small bonus for each keyword found in title
            }
        }
        // Cap title bonus to avoid over-inflation by many small keywords
        currentScore += Math.min(titleBonus, 0.25);
        // Bonus for exact keyword matches in description (smaller bonus)
        let descriptionBonus = 0;
        for (const keyword of keywords) {
            if (eventDescriptionLower.includes(keyword)) {
                descriptionBonus += 0.025;
            }
        }
        currentScore += Math.min(descriptionBonus, 0.1);
        // Attendee matching bonus
        let attendeeMatchBonus = 0;
        const maxAttendeeBonus = 0.3; // Max possible bonus from attendees
        if (event.attendees && event.attendees.length > 0) {
            const matchedKeywordsInAttendees = new Set(); // Track keywords that already gave a bonus for this event
            for (const attendeeString of event.attendees) {
                const eventAttendeeName = _extractNameFromAttendeeString(attendeeString);
                if (eventAttendeeName) {
                    for (const keyword of keywords) {
                        // Avoid re-scoring the same keyword if it matched another attendee for this event already
                        if (matchedKeywordsInAttendees.has(keyword))
                            continue;
                        const nameSimilarity = getStringSimilarity(keyword, eventAttendeeName);
                        if (nameSimilarity > 0.7) {
                            // High threshold for name match
                            attendeeMatchBonus += 0.15; // Significant bonus for a good name match
                            matchedKeywordsInAttendees.add(keyword); // Mark this keyword as used for attendee bonus for this event
                            // console.log(`[findCalendarEventByFuzzyReference] Attendee match: keyword "${keyword}" vs attendee "${eventAttendeeName}", similarity ${nameSimilarity.toFixed(3)}`);
                        }
                    }
                }
            }
        }
        currentScore += Math.min(attendeeMatchBonus, maxAttendeeBonus); // Cap attendee bonus
        console.log(`[findCalendarEventByFuzzyReference] Event: "${event.title}", Similarity: ${getStringSimilarity(processedReference, eventTitleLower).toFixed(3)}, TitleBonus: ${titleBonus.toFixed(3)}, DescBonus: ${descriptionBonus.toFixed(3)}, AttendeeBonus: ${attendeeMatchBonus.toFixed(3)}, Final Score: ${currentScore.toFixed(3)}`);
        if (currentScore > highestScore) {
            highestScore = currentScore;
            bestMatch = event;
        }
        else if (currentScore === highestScore && currentScore > 0.01) {
            // Check currentScore > 0.01 to avoid tie-breaking on zero scores
            // If scores are tied, prefer the one that starts sooner
            if (bestMatch && event.startTime < bestMatch.startTime) {
                console.log(`[findCalendarEventByFuzzyReference] Tied score, preferring earlier event: "${event.title}" over "${bestMatch.title}"`);
                bestMatch = event;
            }
        }
    }
    // Adjust minimum score threshold for similarity scores (0.0 to 1.0 range)
    const minimumScoreThreshold = 0.3;
    if (bestMatch && highestScore >= minimumScoreThreshold) {
        console.log(`[findCalendarEventByFuzzyReference] Best match found: "${bestMatch.title}" with score ${highestScore.toFixed(3)} (Threshold: ${minimumScoreThreshold})`);
        return bestMatch;
    }
    else {
        if (bestMatch) {
            // A best match was found, but it didn't meet the threshold
            console.log(`[findCalendarEventByFuzzyReference] A potential match "${bestMatch.title}" was found with score ${highestScore.toFixed(3)}, but it's below the threshold of ${minimumScoreThreshold}.`);
        }
        else {
            // No events scored > 0 or no events at all after filtering
            console.log(`[findCalendarEventByFuzzyReference] No event scored above 0 or no events to score.`);
        }
        console.log(`[findCalendarEventByFuzzyReference] No event met the minimum score threshold (${minimumScoreThreshold}).`);
        return undefined;
    }
}
// Helper function to mock fetching calendar events
async function mockFetchUserCalendarEvents(userId, startDate, endDate) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // Midnight today
    const sampleEvents = [
        {
            id: 'evt1',
            title: 'Project Phoenix Sync-Up',
            startTime: new Date(new Date(today).setDate(today.getDate() + 1)),
            endTime: new Date(new Date(today).setDate(today.getDate() + 1)),
            description: 'Weekly sync for Project Phoenix.',
            attendees: [
                'currentUser@example.com',
                'Mark Johnson <mark.j@example.com>',
                'team.member.jane@example.com',
            ],
            organizer: 'mark.j@example.com',
        },
        {
            id: 'evt2',
            title: 'Marketing Strategy Meeting',
            startTime: new Date(new Date(today).setDate(today.getDate() + 2)),
            endTime: new Date(new Date(today).setDate(today.getDate() + 2)),
            description: 'Discuss Q3 marketing strategy with Alice and the team.',
            attendees: [
                'currentUser@example.com',
                'Alice Wonderland <alice.w@example.com>',
                'marketing_lead@example.com',
                'Bob (Guest)',
            ],
            location: 'Conference Room B',
            organizer: 'marketing_lead@example.com',
        },
        {
            id: 'evt3',
            title: '1:1 with Sarah Miller', // More specific title
            startTime: new Date(new Date(today).setDate(today.getDate() + 3)),
            endTime: new Date(new Date(today).setDate(today.getDate() + 3)),
            attendees: ['currentUser@example.com', 'Sarah Miller <sarahm@corp.com>'], // Specific manager name
            organizer: 'sarahm@corp.com',
        },
        {
            id: 'evt4',
            title: 'Team Lunch',
            startTime: new Date(new Date(today).setDate(today.getDate() + 7)),
            endTime: new Date(new Date(today).setDate(today.getDate() + 7)),
            description: 'Casual team lunch at The Eatery.',
            attendees: [
                'currentUser@example.com',
                'Mark Johnson <mark.j@example.com>',
                'team.member.jane@example.com',
                'Alice Wonderland <alice.w@example.com>',
            ],
            location: 'The Eatery',
            organizer: 'currentUser@example.com',
        },
        {
            id: 'evt5',
            title: 'Budget Review Q2',
            startTime: new Date(new Date(today).setDate(today.getDate() - 7)),
            endTime: new Date(new Date(today).setDate(today.getDate() - 7)),
            description: 'Final review of Q2 budget.',
            attendees: [
                'currentUser@example.com',
                'finance_dept@example.com',
                'Sarah Miller <sarahm@corp.com>',
            ],
            organizer: 'finance_dept@example.com',
        },
        {
            id: 'evt6',
            title: 'Project Phoenix - Critical Path Discussion',
            startTime: new Date(new Date(today).setDate(today.getDate() + 1)),
            endTime: new Date(new Date(today).setDate(today.getDate() + 1)),
            description: 'Urgent discussion on Project Phoenix blockers with Mark.',
            attendees: [
                'currentUser@example.com',
                'Mark Johnson <mark.j@example.com>',
                'cto@example.com',
            ],
            organizer: 'cto@example.com',
        },
        {
            // New event for attendee matching
            id: 'evt7',
            title: 'Planning Session',
            startTime: new Date(new Date(today).setDate(today.getDate() + 4)), // 4 days from now 10 AM
            endTime: new Date(new Date(today).setDate(today.getDate() + 4)), // 4 days from now 12 PM
            description: 'General planning meeting.',
            attendees: [
                'currentUser@example.com',
                'Alice Wonderland <alice.w@example.com>',
                'Bob The Builder <bob@build.it>',
                'Charlie <charlie.doe@email.com>',
            ],
            organizer: 'currentUser@example.com',
        },
    ];
    // Adjust fixed times for sample events to be relative to 'today' for consistent testing
    sampleEvents.forEach((event) => {
        if (event.id === 'evt1') {
            event.startTime.setHours(9, 0, 0, 0);
            event.endTime.setHours(10, 0, 0, 0); // Tomorrow 9 AM
        }
        else if (event.id === 'evt2') {
            event.startTime.setHours(14, 0, 0, 0);
            event.endTime.setHours(15, 0, 0, 0); // Day after tomorrow 2 PM
        }
        else if (event.id === 'evt3') {
            event.startTime.setHours(11, 0, 0, 0);
            event.endTime.setHours(11, 30, 0, 0); // 3 days from now 11 AM
        }
        else if (event.id === 'evt4') {
            event.startTime.setHours(12, 0, 0, 0);
            event.endTime.setHours(13, 0, 0, 0); // Next week 12 PM
        }
        else if (event.id === 'evt5') {
            event.startTime.setHours(15, 0, 0, 0);
            event.endTime.setHours(16, 0, 0, 0); // Last week 3 PM
        }
        else if (event.id === 'evt6') {
            event.startTime.setHours(14, 0, 0, 0);
            event.endTime.setHours(15, 0, 0, 0); // Tomorrow 2 PM
        }
        else if (event.id === 'evt7') {
            event.startTime.setHours(10, 0, 0, 0);
            event.endTime.setHours(12, 0, 0, 0); // 4 days from now 10 AM
        }
    });
    console.log(`[mockFetchUserCalendarEvents] Mock UserID: ${userId}. Filtering events between ${startDate.toISOString()} and ${endDate.toISOString()}`);
    const filteredEvents = sampleEvents.filter((event) => {
        return event.startTime >= startDate && event.startTime <= endDate;
    });
    console.log(`[mockFetchUserCalendarEvents] Returning ${filteredEvents.length} mock events after filtering.`);
    return Promise.resolve(filteredEvents);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kYXJTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxlbmRhclNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQXVNQSw4RUF1TUM7QUE3WEQsTUFBTSxVQUFVLEdBQWE7SUFDM0IsR0FBRztJQUNILElBQUk7SUFDSixLQUFLO0lBQ0wsS0FBSztJQUNMLElBQUk7SUFDSixJQUFJO0lBQ0osSUFBSTtJQUNKLEtBQUs7SUFDTCxJQUFJO0lBQ0osS0FBSztJQUNMLElBQUk7SUFDSixJQUFJO0lBQ0osTUFBTTtJQUNOLElBQUk7SUFDSixJQUFJO0lBQ0osS0FBSztJQUNMLElBQUk7SUFDSixJQUFJO0lBQ0osS0FBSztJQUNMLElBQUk7SUFDSixJQUFJO0lBQ0osSUFBSTtJQUNKLE1BQU07SUFDTixNQUFNO0lBQ04sS0FBSztJQUNMLE9BQU87SUFDUCxNQUFNO0lBQ04sT0FBTztJQUNQLE9BQU87SUFDUCxNQUFNO0lBQ04sTUFBTTtJQUNOLElBQUk7SUFDSixLQUFLO0lBQ0wsTUFBTTtJQUNOLE1BQU07SUFDTixHQUFHO0lBQ0gsSUFBSTtJQUNKLEtBQUs7SUFDTCxJQUFJO0lBQ0osS0FBSztJQUNMLElBQUk7SUFDSixJQUFJO0lBQ0osSUFBSTtJQUNKLElBQUksRUFBRSxxREFBcUQ7Q0FDNUQsQ0FBQztBQUVGOzs7OztHQUtHO0FBQ0gsU0FBUyxVQUFVLENBQUMsR0FBVyxFQUFFLElBQVksQ0FBQztJQUM1QyxNQUFNLFVBQVUsR0FBRyxHQUFHLENBQUMsV0FBVyxFQUFFLENBQUMsT0FBTyxDQUFDLFlBQVksRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLHFDQUFxQztJQUNyRyxJQUFJLFVBQVUsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7UUFDMUIsT0FBTyxFQUFFLENBQUM7SUFDWixDQUFDO0lBQ0QsTUFBTSxNQUFNLEdBQWEsRUFBRSxDQUFDO0lBQzVCLEtBQUssSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFF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QUFPLENBQUMsY0FBYyxDQUFDLENBQUM7QUFDekMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8qKlxuICogUmVwcmVzZW50cyBhIHN1bW1hcnkgb2YgYSBjYWxlbmRhciBldmVudC5cbiAqIFRoaXMgc3RydWN0dXJlIHdpbGwgbmVlZCB0byBiZSBkZWZpbmVkIGJhc2VkIG9uIHRoZSBhY3R1YWwgZGF0YSBhdmFpbGFibGVcbiAqIGZyb20gdGhlIGNhbGVuZGFyIEFQSSBhbmQgdGhlIG5lZWRzIG9mIHRoZSBQcm9hY3RpdmUgTWVldGluZyBQcmVwIEFzc2lzdGFudC5cbiAqL1xuZXhwb3J0IGludGVyZmFjZSBDYWxlbmRhckV2ZW50U3VtbWFyeSB7XG4gIGlkOiBzdHJpbmc7XG4gIHRpdGxlOiBzdHJpbmc7XG4gIHN0YXJ0VGltZTogRGF0ZTtcbiAgZW5kVGltZTogRGF0ZTtcbiAgZGVzY3JpcHRpb24/OiBzdHJpbmc7XG4gIGF0dGVuZGVlcz86IHN0cmluZ1tdOyAvLyBlLmcuLCBsaXN0IG9mIGVtYWlsIGFkZHJlc3NlcyBvciBuYW1lc1xuICBsb2NhdGlvbj86IHN0cmluZztcbiAgb3JnYW5pemVyPzogc3RyaW5nO1xuICAvLyBQb3RlbnRpYWxseSBvdGhlciByZWxldmFudCBmaWVsZHMgbGlrZSBtZWV0aW5nIGxpbmssIGV0Yy5cbn1cblxuY29uc3QgU1RPUF9XT1JEUzogc3RyaW5nW10gPSBbXG4gICdhJyxcbiAgJ2FuJyxcbiAgJ2FuZCcsXG4gICdhcmUnLFxuICAnYXMnLFxuICAnYXQnLFxuICAnYmUnLFxuICAnYnV0JyxcbiAgJ2J5JyxcbiAgJ2ZvcicsXG4gICdpZicsXG4gICdpbicsXG4gICdpbnRvJyxcbiAgJ2lzJyxcbiAgJ2l0JyxcbiAgJ2l0cycsXG4gICdteScsXG4gICdubycsXG4gICdub3QnLFxuICAnb2YnLFxuICAnb24nLFxuICAnb3InLFxuICAnc3VjaCcsXG4gICd0aGF0JyxcbiAgJ3RoZScsXG4gICd0aGVpcicsXG4gICd0aGVuJyxcbiAgJ3RoZXJlJyxcbiAgJ3RoZXNlJyxcbiAgJ3RoZXknLFxuICAndGhpcycsXG4gICd0bycsXG4gICd3YXMnLFxuICAnd2lsbCcsXG4gICd3aXRoJyxcbiAgJ2knLFxuICAnbWUnLFxuICAneW91JyxcbiAgJ2hlJyxcbiAgJ3NoZScsXG4gICd3ZScsXG4gICd1cycsXG4gICdhbScsXG4gICdwbScsIC8vIGFsc28gdGltZSBpbmRpY2F0b3JzIGlmIG5vdCBoYW5kbGVkIGJ5IGRhdGUgcGFyc2VyXG5dO1xuXG4vKipcbiAqIEdlbmVyYXRlcyBuLWdyYW1zIChzcGVjaWZpY2FsbHkgYmlncmFtcykgZnJvbSBhIHN0cmluZy5cbiAqIEBwYXJhbSBzdHIgVGhlIGlucHV0IHN0cmluZy5cbiAqIEBwYXJhbSBuIFRoZSBzaXplIG9mIHRoZSBuLWdyYW1zIChkZWZhdWx0IGlzIDIgZm9yIGJpZ3JhbXMpLlxuICogQHJldHVybnMgQW4gYXJyYXkgb2Ygbi1ncmFtcy5cbiAqL1xuZnVuY3Rpb24gX2dldE5ncmFtcyhzdHI6IHN0cmluZywgbjogbnVtYmVyID0gMik6IHN0cmluZ1tdIHtcbiAgY29uc3QgY2xlYW5lZFN0ciA9IHN0ci50b0xvd2VyQ2FzZSgpLnJlcGxhY2UoL1teYS16MC05XS9nLCAnJyk7IC8vIEtlZXAgb25seSBhbHBoYW51bWVyaWMgZm9yIG4tZ3JhbXNcbiAgaWYgKGNsZWFuZWRTdHIubGVuZ3RoIDwgbikge1xuICAgIHJldHVybiBbXTtcbiAgfVxuICBjb25zdCBuZ3JhbXM6IHN0cmluZ1tdID0gW107XG4gIGZvciAobGV0IGkgPSAwOyBpIDw9IGNsZWFuZWRTdHIubGVuZ3RoIC0gbjsgaSsrKSB7XG4gICAgbmdyYW1zLnB1c2goY2xlYW5lZFN0ci5zdWJzdHJpbmcoaSwgaSArIG4pKTtcbiAgfVxuICByZXR1cm4gbmdyYW1zO1xufVxuXG4vKipcbiAqIENhbGN1bGF0ZXMgc3RyaW5nIHNpbWlsYXJpdHkgYmFzZWQgb24gbi1ncmFtIGNvbXBhcmlzb24gKFPDuHJlbnNlbi1EaWNlIGNvZWZmaWNpZW50KS5cbiAqIEBwYXJhbSBzdHIxIEZpcnN0IHN0cmluZy5cbiAqIEBwYXJhbSBzdHIyIFNlY29uZCBzdHJpbmcuXG4gKiBAcGFyYW0gbiBOLWdyYW0gc2l6ZSAoZGVmYXVsdCAyIGZvciBiaWdyYW1zKS5cbiAqIEByZXR1cm5zIFNpbWlsYXJpdHkgc2NvcmUgYmV0d2VlbiAwIGFuZCAxLlxuICovXG5mdW5jdGlvbiBnZXRTdHJpbmdTaW1pbGFyaXR5KFxuICBzdHIxOiBzdHJpbmcsXG4gIHN0cjI6IHN0cmluZyxcbiAgbjogbnVtYmVyID0gMlxuKTogbnVtYmVyIHtcbiAgaWYgKCFzdHIxIHx8ICFzdHIyKSB7XG4gICAgcmV0dXJuIDA7XG4gIH1cbiAgLy8gTm9ybWFsaXplIHN0cmluZ3MgZm9yIGNvbXBhcmlzb24gYmV5b25kIGp1c3Qgbi1ncmFtIGdlbmVyYXRpb24gKGUuZy4gZnVsbCBzdHJpbmcgaWYgc2hvcnQpXG4gIGNvbnN0IHMxID0gc3RyMS50b0xvd2VyQ2FzZSgpLnJlcGxhY2UoL1xccysvZywgJycpO1xuICBjb25zdCBzMiA9IHN0cjIudG9Mb3dlckNhc2UoKS5yZXBsYWNlKC9cXHMrL2csICcnKTtcblxuICBpZiAoczEgPT09IHMyKSB7XG4gICAgLy8gRXhhY3QgbWF0Y2ggYWZ0ZXIgbm9ybWFsaXphdGlvblxuICAgIHJldHVybiAxLjA7XG4gIH1cblxuICBjb25zdCBuZ3JhbXMxID0gX2dldE5ncmFtcyhzMSwgbik7XG4gIGNvbnN0IG5ncmFtczIgPSBfZ2V0TmdyYW1zKHMyLCBuKTtcblxuICBpZiAobmdyYW1zMS5sZW5ndGggPT09IDAgfHwgbmdyYW1zMi5sZW5ndGggPT09IDApIHtcbiAgICByZXR1cm4gMDtcbiAgfVxuXG4gIGNvbnN0IHNldDEgPSBuZXcgU2V0KG5ncmFtczEpO1xuICBjb25zdCBzZXQyID0gbmV3IFNldChuZ3JhbXMyKTtcbiAgbGV0IGNvbW1vbkNvdW50ID0gMDtcblxuICBmb3IgKGNvbnN0IG5ncmFtIG9mIHNldDEpIHtcbiAgICBpZiAoc2V0Mi5oYXMobmdyYW0pKSB7XG4gICAgICAvLyBGb3IgYWN0dWFsIERpY2UsIHlvdSdkIGNvdW50IG9jY3VycmVuY2VzIGluIGxpc3RzLCBub3QganVzdCBwcmVzZW5jZSBpbiBzZXRzLFxuICAgICAgLy8gaWYgc3RyaW5ncyBjYW4gaGF2ZSByZXBlYXRlZCBuLWdyYW1zLiBGb3Igc2ltcGxpY2l0eSB3aXRoIHNldHM6XG4gICAgICBjb21tb25Db3VudCsrO1xuICAgIH1cbiAgfVxuICAvLyBTaW1wbGlmaWVkIERpY2UgZm9yIHNldHM6ICgyICogfEludGVyc2VjdGlvbnwpIC8gKHxTZXQxfCArIHxTZXQyfClcbiAgLy8gTW9yZSBhY2N1cmF0ZSBEaWNlIGZvciBiYWdzIChtdWx0aXNldHMpIG9mIG5ncmFtczogKDIgKiBjb21tb25OZ3JhbXNDb3VudCkgLyAobmdyYW1zMS5sZW5ndGggKyBuZ3JhbXMyLmxlbmd0aClcbiAgLy8gTGV0J3MgZG8gdGhlIG1vcmUgYWNjdXJhdGUgb25lIGJ5IGl0ZXJhdGluZyB0aHJvdWdoIG9uZSBsaXN0IGFuZCByZW1vdmluZyBmcm9tIGEgY29weSBvZiB0aGUgb3RoZXIuXG5cbiAgY29tbW9uQ291bnQgPSAwO1xuICBjb25zdCBuZ3JhbXMyQ29weSA9IFsuLi5uZ3JhbXMyXTtcbiAgZm9yIChjb25zdCBuZ3JhbSBvZiBuZ3JhbXMxKSB7XG4gICAgY29uc3QgaW5kZXhJbkNvcHkgPSBuZ3JhbXMyQ29weS5pbmRleE9mKG5ncmFtKTtcbiAgICBpZiAoaW5kZXhJbkNvcHkgIT09IC0xKSB7XG4gICAgICBjb21tb25Db3VudCsrO1xuICAgICAgbmdyYW1zMkNvcHkuc3BsaWNlKGluZGV4SW5Db3B5LCAxKTsgLy8gUmVtb3ZlIHRvIGhhbmRsZSBkdXBsaWNhdGVzIGNvcnJlY3RseVxuICAgIH1cbiAgfVxuXG4gIHJldHVybiAoMiAqIGNvbW1vbkNvdW50KSAvIChuZ3JhbXMxLmxlbmd0aCArIG5ncmFtczIubGVuZ3RoKTtcbn1cblxuLyoqXG4gKiBFeHRyYWN0cyBhIGRpc3BsYXkgbmFtZSBmcm9tIGEgdHlwaWNhbCBjYWxlbmRhciBhdHRlbmRlZSBzdHJpbmcuXG4gKiBAcGFyYW0gYXR0ZW5kZWVTdHJpbmcgVGhlIHJhdyBhdHRlbmRlZSBzdHJpbmcgKGUuZy4sIFwiSm9obiBEb2UgPGpvaG4uZG9lQGV4YW1wbGUuY29tPlwiLCBcImphbmVAZXhhbXBsZS5jb21cIikuXG4gKiBAcmV0dXJucyBBIGxvd2VyY2FzZSwgY2xlYW5lZCBuYW1lIHBhcnQgb3IgYW4gZW1wdHkgc3RyaW5nLlxuICovXG5mdW5jdGlvbiBfZXh0cmFjdE5hbWVGcm9tQXR0ZW5kZWVTdHJpbmcoYXR0ZW5kZWVTdHJpbmc6IHN0cmluZyk6IHN0cmluZyB7XG4gIGlmICghYXR0ZW5kZWVTdHJpbmcpIHJldHVybiAnJztcblxuICBhdHRlbmRlZVN0cmluZyA9IGF0dGVuZGVlU3RyaW5nLnRvTG93ZXJDYXNlKCk7XG5cbiAgLy8gQ2FzZSAxOiBcIkZ1bGxOYW1lIDxlbWFpbD5cIiBvciBcIkZpcnN0TmFtZSA8ZW1haWw+XCJcbiAgY29uc3QgZW1haWxNYXRjaCA9IGF0dGVuZGVlU3RyaW5nLm1hdGNoKC9eKC4qPyk8Lio+JC8pO1xuICBpZiAoZW1haWxNYXRjaCAmJiBlbWFpbE1hdGNoWzFdKSB7XG4gICAgcmV0dXJuIGVtYWlsTWF0Y2hbMV0udHJpbSgpO1xuICB9XG5cbiAgLy8gQ2FzZSAyOiBcIk5hbWUgKEd1ZXN0KVwiIG9yIFwiTmFtZSAoRXh0ZXJuYWwpXCJcbiAgY29uc3QgZ3Vlc3RNYXRjaCA9IGF0dGVuZGVlU3RyaW5nLm1hdGNoKC9eKC4qPylcXHMqXFwoKGd1ZXN0fGV4dGVybmFsKVxcKS8pO1xuICBpZiAoZ3Vlc3RNYXRjaCAmJiBndWVzdE1hdGNoWzFdKSB7XG4gICAgcmV0dXJuIGd1ZXN0TWF0Y2hbMV0udHJpbSgpO1xuICB9XG5cbiAgLy8gQ2FzZSAzOiBKdXN0IGFuIGVtYWlsIFwidXNlckBleGFtcGxlLmNvbVwiIC0+IFwidXNlclwiXG4gIGlmIChhdHRlbmRlZVN0cmluZy5pbmNsdWRlcygnQCcpKSB7XG4gICAgY29uc3QgcGFydHMgPSBhdHRlbmRlZVN0cmluZy5zcGxpdCgnQCcpO1xuICAgIC8vIEZ1cnRoZXIgY2xlYW4gdXNlcm5hbWUgcGFydCBpZiBpdCBjb250YWlucyBkb3RzIG9yIG51bWJlcnMgdGhhdCBhcmUgbm90IHBhcnQgb2YgdHlwaWNhbCBmaXJzdC9sYXN0IG5hbWVzXG4gICAgLy8gRm9yIHNpbXBsaWNpdHkgaGVyZSwganVzdCB0YWtpbmcgdGhlIHBhcnQgYmVmb3JlIEAuIE1vcmUgc29waGlzdGljYXRlZCBjbGVhbmluZyBjb3VsZCBiZSBhZGRlZC5cbiAgICByZXR1cm4gcGFydHNbMF0ucmVwbGFjZSgvW15hLXpcXHMnLV0vZ2ksICcnKS50cmltKCk7IC8vIEtlZXAgbGV0dGVycywgc3BhY2VzLCBoeXBoZW5zLCBhcG9zdHJvcGhlc1xuICB9XG5cbiAgLy8gQ2FzZSA0OiBKdXN0IGEgbmFtZSAobm8gZW1haWwsIG5vIGd1ZXN0IG1hcmtlcilcbiAgLy8gQ2xlYW4gaXQgc2ltaWxhcmx5IHRvIHRoZSBlbWFpbCB1c2VybmFtZSBwYXJ0XG4gIHJldHVybiBhdHRlbmRlZVN0cmluZy5yZXBsYWNlKC9bXmEtelxccyctXS9naSwgJycpLnRyaW0oKTtcbn1cblxuLyoqXG4gKiBPcHRpb25hbCBkYXRlIGhpbnRzIHRvIG5hcnJvdyBkb3duIHRoZSBzZWFyY2ggZm9yIGEgY2FsZW5kYXIgZXZlbnQuXG4gKiAtIHNwZWNpZmljRGF0ZTogTG9va3MgZm9yIGV2ZW50cyBvbiB0aGlzIHBhcnRpY3VsYXIgZGF5LlxuICogLSBzdGFydERhdGUvZW5kRGF0ZTogRGVmaW5lcyBhIHdpbmRvdyB0byBzZWFyY2ggZm9yIGV2ZW50cy5cbiAqIElmIG11bHRpcGxlIGhpbnRzIGFyZSBwcm92aWRlZCwgdGhlIG5hcnJvd2VzdCBwb3NzaWJsZSByYW5nZSBzaG91bGQgYmUgcHJpb3JpdGl6ZWQuXG4gKiBGb3IgZXhhbXBsZSwgaWYgc3BlY2lmaWNEYXRlIGlzIGdpdmVuLCBzdGFydERhdGUgYW5kIGVuZERhdGUgbWlnaHQgYmUgaWdub3JlZCBvciB1c2VkIGFzIHZhbGlkYXRpb24uXG4gKi9cbmV4cG9ydCBpbnRlcmZhY2UgRGF0ZUhpbnRzIHtcbiAgc3BlY2lmaWNEYXRlPzogRGF0ZTsgLy8gZS5nLiwgXCJmaW5kIG15IG1lZXRpbmcgb24gMjAyNC0wMy0xNVwiXG4gIHN0YXJ0RGF0ZT86IERhdGU7IC8vIGUuZy4sIFwibXkgbWVldGluZyBzb21ldGltZSBhZnRlciBuZXh0IE1vbmRheVwiXG4gIGVuZERhdGU/OiBEYXRlOyAvLyBlLmcuLCBcIm15IG1lZXRpbmcgYmVmb3JlIHRoZSBlbmQgb2YgbmV4dCB3ZWVrXCJcbn1cblxuLyoqXG4gKiBGaW5kcyBhIGNhbGVuZGFyIGV2ZW50IGJhc2VkIG9uIGEgbmF0dXJhbCBsYW5ndWFnZSByZWZlcmVuY2UgYW5kIG9wdGlvbmFsIGRhdGUgaGludHMuXG4gKlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIgd2hvc2UgY2FsZW5kYXIgaXMgdG8gYmUgc2VhcmNoZWQuXG4gKiBAcGFyYW0gbWVldGluZ19yZWZlcmVuY2UgQSBuYXR1cmFsIGxhbmd1YWdlIHN0cmluZyBkZXNjcmliaW5nIHRoZSBtZWV0aW5nXG4gKiAgICAgICAgICAgICAgICAgICAgICAgICAgKGUuZy4sIFwibXkgc3luYyB1cCB0b21vcnJvd1wiLCBcImJ1ZGdldCByZXZpZXcgbmV4dCB3ZWVrXCIpLlxuICogQHBhcmFtIGRhdGVfaGludHMgT3B0aW9uYWwgaGludHMgdG8gbmFycm93IGRvd24gdGhlIGRhdGUgcmFuZ2UgZm9yIHRoZSBzZWFyY2guXG4gKiBAcmV0dXJucyBBIFByb21pc2UgdGhhdCByZXNvbHZlcyB0byBhIENhbGVuZGFyRXZlbnRTdW1tYXJ5IGlmIGEgc3VpdGFibGUgZXZlbnRcbiAqICAgICAgICAgIGlzIGZvdW5kLCBvciB1bmRlZmluZWQgb3RoZXJ3aXNlLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZmluZENhbGVuZGFyRXZlbnRCeUZ1enp5UmVmZXJlbmNlKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgbWVldGluZ19yZWZlcmVuY2U6IHN0cmluZyxcbiAgZGF0ZV9oaW50cz86IERhdGVIaW50c1xuKTogUHJvbWlzZTxDYWxlbmRhckV2ZW50U3VtbWFyeSB8IHVuZGVmaW5lZD4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBgW2ZpbmRDYWxlbmRhckV2ZW50QnlGdXp6eVJlZmVyZW5jZV0gSW5wdXRzOiB1c2VySWQ9JHt1c2VySWR9LCByZWZlcmVuY2U9XCIke21lZXRpbmdfcmVmZXJlbmNlfVwiLCBoaW50cz0ke0pTT04uc3RyaW5naWZ5KGRhdGVfaGludHMpfWBcbiAgKTtcblxuICAvLyAxLiBEZXRlcm1pbmUgc2VhcmNoIHdpbmRvdyBiYXNlZCBvbiBkYXRlX2hpbnRzIG9yIGRlZmF1bHRzLlxuICBsZXQgc2VhcmNoV2luZG93U3RhcnQ6IERhdGU7XG4gIGxldCBzZWFyY2hXaW5kb3dFbmQ6IERhdGU7XG4gIGNvbnN0IG5vdyA9IG5ldyBEYXRlKCk7XG5cbiAgaWYgKGRhdGVfaGludHM/LnNwZWNpZmljRGF0ZSkge1xuICAgIHNlYXJjaFdpbmRvd1N0YXJ0ID0gbmV3IERhdGUoZGF0ZV9oaW50cy5zcGVjaWZpY0RhdGUpO1xuICAgIHNlYXJjaFdpbmRvd1N0YXJ0LnNldEhvdXJzKDAsIDAsIDAsIDApOyAvLyBTdGFydCBvZiB0aGUgZGF5XG4gICAgc2VhcmNoV2luZG93RW5kID0gbmV3IERhdGUoZGF0ZV9oaW50cy5zcGVjaWZpY0RhdGUpO1xuICAgIHNlYXJjaFdpbmRvd0VuZC5zZXRIb3VycygyMywgNTksIDU5LCA5OTkpOyAvLyBFbmQgb2YgdGhlIGRheVxuICB9IGVsc2UgaWYgKGRhdGVfaGludHM/LnN0YXJ0RGF0ZSAmJiBkYXRlX2hpbnRzPy5lbmREYXRlKSB7XG4gICAgc2VhcmNoV2luZG93U3RhcnQgPSBuZXcgRGF0ZShkYXRlX2hpbnRzLnN0YXJ0RGF0ZSk7XG4gICAgc2VhcmNoV2luZG93RW5kID0gbmV3IERhdGUoZGF0ZV9oaW50cy5lbmREYXRlKTtcbiAgfSBlbHNlIGlmIChkYXRlX2hpbnRzPy5zdGFydERhdGUpIHtcbiAgICBzZWFyY2hXaW5kb3dTdGFydCA9IG5ldyBEYXRlKGRhdGVfaGludHMuc3RhcnREYXRlKTtcbiAgICBzZWFyY2hXaW5kb3dFbmQgPSBuZXcgRGF0ZShzZWFyY2hXaW5kb3dTdGFydCk7XG4gICAgc2VhcmNoV2luZG93RW5kLnNldERhdGUoc2VhcmNoV2luZG93U3RhcnQuZ2V0RGF0ZSgpICsgMTQpOyAvLyBEZWZhdWx0IDIgd2Vla3Mgd2luZG93XG4gICAgc2VhcmNoV2luZG93RW5kLnNldEhvdXJzKDIzLCA1OSwgNTksIDk5OSk7XG4gIH0gZWxzZSBpZiAoZGF0ZV9oaW50cz8uZW5kRGF0ZSkge1xuICAgIHNlYXJjaFdpbmRvd0VuZCA9IG5ldyBEYXRlKGRhdGVfaGludHMuZW5kRGF0ZSk7XG4gICAgc2VhcmNoV2luZG93U3RhcnQgPSBuZXcgRGF0ZShzZWFyY2hXaW5kb3dFbmQpO1xuICAgIHNlYXJjaFdpbmRvd1N0YXJ0LnNldERhdGUoc2VhcmNoV2luZG93RW5kLmdldERhdGUoKSAtIDE0KTsgLy8gRGVmYXVsdCAyIHdlZWtzIHdpbmRvdyBwcmlvclxuICAgIHNlYXJjaFdpbmRvd1N0YXJ0LnNldEhvdXJzKDAsIDAsIDAsIDApO1xuICB9IGVsc2Uge1xuICAgIC8vIERlZmF1bHQgc2VhcmNoIHdpbmRvdzogZnJvbSBzdGFydCBvZiB0b2RheSB0byAxNCBkYXlzIGluIHRoZSBmdXR1cmVcbiAgICBzZWFyY2hXaW5kb3dTdGFydCA9IG5ldyBEYXRlKG5vdyk7XG4gICAgc2VhcmNoV2luZG93U3RhcnQuc2V0SG91cnMoMCwgMCwgMCwgMCk7XG4gICAgc2VhcmNoV2luZG93RW5kID0gbmV3IERhdGUobm93KTtcbiAgICBzZWFyY2hXaW5kb3dFbmQuc2V0RGF0ZShub3cuZ2V0RGF0ZSgpICsgMTQpO1xuICAgIHNlYXJjaFdpbmRvd0VuZC5zZXRIb3VycygyMywgNTksIDU5LCA5OTkpO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgYFtmaW5kQ2FsZW5kYXJFdmVudEJ5RnV6enlSZWZlcmVuY2VdIERldGVybWluZWQgc2VhcmNoIHdpbmRvdzogJHtzZWFyY2hXaW5kb3dTdGFydC50b0lTT1N0cmluZygpfSB0byAke3NlYXJjaFdpbmRvd0VuZC50b0lTT1N0cmluZygpfWBcbiAgKTtcblxuICAvLyAyLiBGZXRjaCBjYWxlbmRhciBldmVudHMgZm9yIHRoZSB1c2VyIHdpdGhpbiB0aGF0IHdpbmRvdyAobW9ja2VkIGZvciBub3cpLlxuICBjb25zdCBtb2NrRXZlbnRzID0gYXdhaXQgbW9ja0ZldGNoVXNlckNhbGVuZGFyRXZlbnRzKFxuICAgIHVzZXJJZCxcbiAgICBzZWFyY2hXaW5kb3dTdGFydCxcbiAgICBzZWFyY2hXaW5kb3dFbmRcbiAgKTtcbiAgY29uc29sZS5sb2coXG4gICAgYFtmaW5kQ2FsZW5kYXJFdmVudEJ5RnV6enlSZWZlcmVuY2VdIEZldGNoZWQgJHttb2NrRXZlbnRzLmxlbmd0aH0gbW9jayBldmVudHMuYFxuICApO1xuXG4gIC8vIDMuIEFwcGx5IG1hdGNoaW5nIGxvZ2ljIChmdXp6eSwga2V5d29yZCwgb3IgTExNLWJhc2VkKSBhZ2FpbnN0IG1lZXRpbmdfcmVmZXJlbmNlLlxuICBpZiAobW9ja0V2ZW50cy5sZW5ndGggPT09IDApIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdbZmluZENhbGVuZGFyRXZlbnRCeUZ1enp5UmVmZXJlbmNlXSBObyBtb2NrIGV2ZW50cyBmb3VuZCBpbiB0aGUgc2VhcmNoIHdpbmRvdy4gUmV0dXJuaW5nIHVuZGVmaW5lZC4nXG4gICAgKTtcbiAgICByZXR1cm4gdW5kZWZpbmVkO1xuICB9XG5cbiAgY29uc3QgbWVldGluZ1JlZmVyZW5jZUxvd2VyID0gbWVldGluZ19yZWZlcmVuY2UudG9Mb3dlckNhc2UoKTtcblxuICAvLyBFbmhhbmNlZCBrZXl3b3JkIGV4dHJhY3Rpb246XG4gIC8vIDEuIFNwbGl0IGJ5IG5vbi1hbHBoYW51bWVyaWMgY2hhcmFjdGVycyAoaGFuZGxlcyBwdW5jdHVhdGlvbiBiZXR0ZXIgdGhhbiBqdXN0IHNwYWNlKVxuICAvLyAyLiBGaWx0ZXIgb3V0IHN0b3Agd29yZHNcbiAgLy8gMy4gRmlsdGVyIG91dCB2ZXJ5IHNob3J0IHdvcmRzIChlLmcuLCA8IDMgY2hhcnMpXG4gIGNvbnN0IHJhd1dvcmRzID0gbWVldGluZ1JlZmVyZW5jZUxvd2VyLnNwbGl0KC9bXmEtejAtOV0rLykuZmlsdGVyKEJvb2xlYW4pOyAvLyBTcGxpdCBhbmQgcmVtb3ZlIGVtcHR5IHN0cmluZ3NcbiAgY29uc3Qga2V5d29yZHMgPSByYXdXb3Jkcy5maWx0ZXIoXG4gICAgKHdvcmQpID0+ICFTVE9QX1dPUkRTLmluY2x1ZGVzKHdvcmQpICYmIHdvcmQubGVuZ3RoID49IDNcbiAgKTtcblxuICBpZiAoa2V5d29yZHMubGVuZ3RoID09PSAwICYmIHJhd1dvcmRzLmxlbmd0aCA+IDApIHtcbiAgICAvLyBJZiBhbGwgd29yZHMgd2VyZSBzdG9wIHdvcmRzIG9yIHRvbyBzaG9ydCwgZmFsbCBiYWNrIHRvIHVzaW5nIGFsbCBzaG9ydCB3b3JkcyBmcm9tIG9yaWdpbmFsIHJlZmVyZW5jZVxuICAgIC8vIHRvIGNhdGNoIGNhc2VzIGxpa2UgXCIxOjFcIiBvciBpZiB0aGUgbWVldGluZyB0aXRsZSBpdHNlbGYgaXMgdmVyeSBzaG9ydCBhbmQgbGlrZSBhIHN0b3Agd29yZC5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdbZmluZENhbGVuZGFyRXZlbnRCeUZ1enp5UmVmZXJlbmNlXSBObyBzaWduaWZpY2FudCBrZXl3b3JkcyBhZnRlciBmaWx0ZXJpbmcsIGZhbGxpbmcgYmFjayB0byByYXcgc2hvcnQgd29yZHMgaWYgYW55LidcbiAgICApO1xuICAgIGtleXdvcmRzLnB1c2goXG4gICAgICAuLi5yYXdXb3Jkcy5maWx0ZXIoKHdvcmQpID0+IHdvcmQubGVuZ3RoID4gMCAmJiB3b3JkLmxlbmd0aCA8IDMpXG4gICAgKTsgLy8gQWRkIGJhY2sgdmVyeSBzaG9ydCB3b3Jkc1xuICAgIGlmIChrZXl3b3Jkcy5sZW5ndGggPT09IDApIHtcbiAgICAgIC8vIElmIHN0aWxsIG5vdGhpbmcsIHVzZSBhbGwgcmF3IHdvcmRzXG4gICAgICBrZXl3b3Jkcy5wdXNoKC4uLnJhd1dvcmRzKTtcbiAgICB9XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW2ZpbmRDYWxlbmRhckV2ZW50QnlGdXp6eVJlZmVyZW5jZV0gRmFsbGJhY2sga2V5d29yZHM6ICR7a2V5d29yZHMuam9pbignLCAnKX1gXG4gICAgKTtcbiAgfVxuXG4gIGNvbnNvbGUubG9nKFxuICAgIGBbZmluZENhbGVuZGFyRXZlbnRCeUZ1enp5UmVmZXJlbmNlXSBQcm9jZXNzZWQgS2V5d29yZHMgZnJvbSByZWZlcmVuY2U6ICR7a2V5d29yZHMuam9pbignLCAnKX1gXG4gICk7XG4gIGNvbnN0IHByb2Nlc3NlZFJlZmVyZW5jZSA9IGtleXdvcmRzLmpvaW4oJyAnKTsgLy8gVXNlIHRoaXMgZm9yIG92ZXJhbGwgc2ltaWxhcml0eVxuXG4gIGxldCBiZXN0TWF0Y2g6IENhbGVuZGFyRXZlbnRTdW1tYXJ5IHwgdW5kZWZpbmVkID0gdW5kZWZpbmVkO1xuICBsZXQgaGlnaGVzdFNjb3JlID0gMC4wOyAvLyBTY29yZXMgYXJlIG5vdyBmbG9hdCAoMC4wIHRvIDEuMCspXG5cbiAgZm9yIChjb25zdCBldmVudCBvZiBtb2NrRXZlbnRzKSB7XG4gICAgY29uc3QgZXZlbnRUaXRsZUxvd2VyID0gZXZlbnQudGl0bGUudG9Mb3dlckNhc2UoKTtcbiAgICBjb25zdCBldmVudERlc2NyaXB0aW9uTG93ZXIgPSBldmVudC5kZXNjcmlwdGlvbj8udG9Mb3dlckNhc2UoKSB8fCAnJztcblxuICAgIC8vIFByaW1hcnkgc2NvcmUgZnJvbSBmdXp6eSBtYXRjaGluZyB0aGUgcHJvY2Vzc2VkIHJlZmVyZW5jZSBhZ2FpbnN0IHRoZSBldmVudCB0aXRsZVxuICAgIGxldCBjdXJyZW50U2NvcmUgPSBnZXRTdHJpbmdTaW1pbGFyaXR5KHByb2Nlc3NlZFJlZmVyZW5jZSwgZXZlbnRUaXRsZUxvd2VyKTtcbiAgICAvLyBjb25zb2xlLmxvZyhgW2ZpbmRDYWxlbmRhckV2ZW50QnlGdXp6eVJlZmVyZW5jZV0gRXZlbnQ6IFwiJHtldmVudC50aXRsZX1cIiwgSW5pdGlhbCBTaW1pbGFyaXR5IFNjb3JlOiAke2N1cnJlbnRTY29yZS50b0ZpeGVkKDMpfWApO1xuXG4gICAgLy8gQm9udXMgZm9yIGV4YWN0IGtleXdvcmQgbWF0Y2hlcyBpbiB0aXRsZVxuICAgIGxldCB0aXRsZUJvbnVzID0gMDtcbiAgICBmb3IgKGNvbnN0IGtleXdvcmQgb2Yga2V5d29yZHMpIHtcbiAgICAgIGlmIChldmVudFRpdGxlTG93ZXIuaW5jbHVkZXMoa2V5d29yZCkpIHtcbiAgICAgICAgdGl0bGVCb251cyArPSAwLjA1OyAvLyBTbWFsbCBib251cyBmb3IgZWFjaCBrZXl3b3JkIGZvdW5kIGluIHRpdGxlXG4gICAgICB9XG4gICAgfVxuICAgIC8vIENhcCB0aXRsZSBib251cyB0byBhdm9pZCBvdmVyLWluZmxhdGlvbiBieSBtYW55IHNtYWxsIGtleXdvcmRzXG4gICAgY3VycmVudFNjb3JlICs9IE1hdGgubWluKHRpdGxlQm9udXMsIDAuMjUpO1xuXG4gICAgLy8gQm9udXMgZm9yIGV4YWN0IGtleXdvcmQgbWF0Y2hlcyBpbiBkZXNjcmlwdGlvbiAoc21hbGxlciBib251cylcbiAgICBsZXQgZGVzY3JpcHRpb25Cb251cyA9IDA7XG4gICAgZm9yIChjb25zdCBrZXl3b3JkIG9mIGtleXdvcmRzKSB7XG4gICAgICBpZiAoZXZlbnREZXNjcmlwdGlvbkxvd2VyLmluY2x1ZGVzKGtleXdvcmQpKSB7XG4gICAgICAgIGRlc2NyaXB0aW9uQm9udXMgKz0gMC4wMjU7XG4gICAgICB9XG4gICAgfVxuICAgIGN1cnJlbnRTY29yZSArPSBNYXRoLm1pbihkZXNjcmlwdGlvbkJvbnVzLCAwLjEpO1xuXG4gICAgLy8gQXR0ZW5kZWUgbWF0Y2hpbmcgYm9udXNcbiAgICBsZXQgYXR0ZW5kZWVNYXRjaEJvbnVzID0gMDtcbiAgICBjb25zdCBtYXhBdHRlbmRlZUJvbnVzID0gMC4zOyAvLyBNYXggcG9zc2libGUgYm9udXMgZnJvbSBhdHRlbmRlZXNcbiAgICBpZiAoZXZlbnQuYXR0ZW5kZWVzICYmIGV2ZW50LmF0dGVuZGVlcy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBtYXRjaGVkS2V5d29yZHNJbkF0dGVuZGVlcyA9IG5ldyBTZXQ8c3RyaW5nPigpOyAvLyBUcmFjayBrZXl3b3JkcyB0aGF0IGFscmVhZHkgZ2F2ZSBhIGJvbnVzIGZvciB0aGlzIGV2ZW50XG4gICAgICBmb3IgKGNvbnN0IGF0dGVuZGVlU3RyaW5nIG9mIGV2ZW50LmF0dGVuZGVlcykge1xuICAgICAgICBjb25zdCBldmVudEF0dGVuZGVlTmFtZSA9XG4gICAgICAgICAgX2V4dHJhY3ROYW1lRnJvbUF0dGVuZGVlU3RyaW5nKGF0dGVuZGVlU3RyaW5nKTtcbiAgICAgICAgaWYgKGV2ZW50QXR0ZW5kZWVOYW1lKSB7XG4gICAgICAgICAgZm9yIChjb25zdCBrZXl3b3JkIG9mIGtleXdvcmRzKSB7XG4gICAgICAgICAgICAvLyBBdm9pZCByZS1zY29yaW5nIHRoZSBzYW1lIGtleXdvcmQgaWYgaXQgbWF0Y2hlZCBhbm90aGVyIGF0dGVuZGVlIGZvciB0aGlzIGV2ZW50IGFscmVhZHlcbiAgICAgICAgICAgIGlmIChtYXRjaGVkS2V5d29yZHNJbkF0dGVuZGVlcy5oYXMoa2V5d29yZCkpIGNvbnRpbnVlO1xuXG4gICAgICAgICAgICBjb25zdCBuYW1lU2ltaWxhcml0eSA9IGdldFN0cmluZ1NpbWlsYXJpdHkoXG4gICAgICAgICAgICAgIGtleXdvcmQsXG4gICAgICAgICAgICAgIGV2ZW50QXR0ZW5kZWVOYW1lXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgaWYgKG5hbWVTaW1pbGFyaXR5ID4gMC43KSB7XG4gICAgICAgICAgICAgIC8vIEhpZ2ggdGhyZXNob2xkIGZvciBuYW1lIG1hdGNoXG4gICAgICAgICAgICAgIGF0dGVuZGVlTWF0Y2hCb251cyArPSAwLjE1OyAvLyBTaWduaWZpY2FudCBib251cyBmb3IgYSBnb29kIG5hbWUgbWF0Y2hcbiAgICAgICAgICAgICAgbWF0Y2hlZEtleXdvcmRzSW5BdHRlbmRlZXMuYWRkKGtleXdvcmQpOyAvLyBNYXJrIHRoaXMga2V5d29yZCBhcyB1c2VkIGZvciBhdHRlbmRlZSBib251cyBmb3IgdGhpcyBldmVudFxuICAgICAgICAgICAgICAvLyBjb25zb2xlLmxvZyhgW2ZpbmRDYWxlbmRhckV2ZW50QnlGdXp6eVJlZmVyZW5jZV0gQXR0ZW5kZWUgbWF0Y2g6IGtleXdvcmQgXCIke2tleXdvcmR9XCIgdnMgYXR0ZW5kZWUgXCIke2V2ZW50QXR0ZW5kZWVOYW1lfVwiLCBzaW1pbGFyaXR5ICR7bmFtZVNpbWlsYXJpdHkudG9GaXhlZCgzKX1gKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG4gICAgY3VycmVudFNjb3JlICs9IE1hdGgubWluKGF0dGVuZGVlTWF0Y2hCb251cywgbWF4QXR0ZW5kZWVCb251cyk7IC8vIENhcCBhdHRlbmRlZSBib251c1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW2ZpbmRDYWxlbmRhckV2ZW50QnlGdXp6eVJlZmVyZW5jZV0gRXZlbnQ6IFwiJHtldmVudC50aXRsZX1cIiwgU2ltaWxhcml0eTogJHtnZXRTdHJpbmdTaW1pbGFyaXR5KHByb2Nlc3NlZFJlZmVyZW5jZSwgZXZlbnRUaXRsZUxvd2VyKS50b0ZpeGVkKDMpfSwgVGl0bGVCb251czogJHt0aXRsZUJvbnVzLnRvRml4ZWQoMyl9LCBEZXNjQm9udXM6ICR7ZGVzY3JpcHRpb25Cb251cy50b0ZpeGVkKDMpfSwgQXR0ZW5kZWVCb251czogJHthdHRlbmRlZU1hdGNoQm9udXMudG9GaXhlZCgzKX0sIEZpbmFsIFNjb3JlOiAke2N1cnJlbnRTY29yZS50b0ZpeGVkKDMpfWBcbiAgICApO1xuXG4gICAgaWYgKGN1cnJlbnRTY29yZSA+IGhpZ2hlc3RTY29yZSkge1xuICAgICAgaGlnaGVzdFNjb3JlID0gY3VycmVudFNjb3JlO1xuICAgICAgYmVzdE1hdGNoID0gZXZlbnQ7XG4gICAgfSBlbHNlIGlmIChjdXJyZW50U2NvcmUgPT09IGhpZ2hlc3RTY29yZSAmJiBjdXJyZW50U2NvcmUgPiAwLjAxKSB7XG4gICAgICAvLyBDaGVjayBjdXJyZW50U2NvcmUgPiAwLjAxIHRvIGF2b2lkIHRpZS1icmVha2luZyBvbiB6ZXJvIHNjb3Jlc1xuICAgICAgLy8gSWYgc2NvcmVzIGFyZSB0aWVkLCBwcmVmZXIgdGhlIG9uZSB0aGF0IHN0YXJ0cyBzb29uZXJcbiAgICAgIGlmIChiZXN0TWF0Y2ggJiYgZXZlbnQuc3RhcnRUaW1lIDwgYmVzdE1hdGNoLnN0YXJ0VGltZSkge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBgW2ZpbmRDYWxlbmRhckV2ZW50QnlGdXp6eVJlZmVyZW5jZV0gVGllZCBzY29yZSwgcHJlZmVycmluZyBlYXJsaWVyIGV2ZW50OiBcIiR7ZXZlbnQudGl0bGV9XCIgb3ZlciBcIiR7YmVzdE1hdGNoLnRpdGxlfVwiYFxuICAgICAgICApO1xuICAgICAgICBiZXN0TWF0Y2ggPSBldmVudDtcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICAvLyBBZGp1c3QgbWluaW11bSBzY29yZSB0aHJlc2hvbGQgZm9yIHNpbWlsYXJpdHkgc2NvcmVzICgwLjAgdG8gMS4wIHJhbmdlKVxuICBjb25zdCBtaW5pbXVtU2NvcmVUaHJlc2hvbGQgPSAwLjM7XG4gIGlmIChiZXN0TWF0Y2ggJiYgaGlnaGVzdFNjb3JlID49IG1pbmltdW1TY29yZVRocmVzaG9sZCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFtmaW5kQ2FsZW5kYXJFdmVudEJ5RnV6enlSZWZlcmVuY2VdIEJlc3QgbWF0Y2ggZm91bmQ6IFwiJHtiZXN0TWF0Y2gudGl0bGV9XCIgd2l0aCBzY29yZSAke2hpZ2hlc3RTY29yZS50b0ZpeGVkKDMpfSAoVGhyZXNob2xkOiAke21pbmltdW1TY29yZVRocmVzaG9sZH0pYFxuICAgICk7XG4gICAgcmV0dXJuIGJlc3RNYXRjaDtcbiAgfSBlbHNlIHtcbiAgICBpZiAoYmVzdE1hdGNoKSB7XG4gICAgICAvLyBBIGJlc3QgbWF0Y2ggd2FzIGZvdW5kLCBidXQgaXQgZGlkbid0IG1lZXQgdGhlIHRocmVzaG9sZFxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBbZmluZENhbGVuZGFyRXZlbnRCeUZ1enp5UmVmZXJlbmNlXSBBIHBvdGVudGlhbCBtYXRjaCBcIiR7YmVzdE1hdGNoLnRpdGxlfVwiIHdhcyBmb3VuZCB3aXRoIHNjb3JlICR7aGlnaGVzdFNjb3JlLnRvRml4ZWQoMyl9LCBidXQgaXQncyBiZWxvdyB0aGUgdGhyZXNob2xkIG9mICR7bWluaW11bVNjb3JlVGhyZXNob2xkfS5gXG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICAvLyBObyBldmVudHMgc2NvcmVkID4gMCBvciBubyBldmVudHMgYXQgYWxsIGFmdGVyIGZpbHRlcmluZ1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBbZmluZENhbGVuZGFyRXZlbnRCeUZ1enp5UmVmZXJlbmNlXSBObyBldmVudCBzY29yZWQgYWJvdmUgMCBvciBubyBldmVudHMgdG8gc2NvcmUuYFxuICAgICAgKTtcbiAgICB9XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW2ZpbmRDYWxlbmRhckV2ZW50QnlGdXp6eVJlZmVyZW5jZV0gTm8gZXZlbnQgbWV0IHRoZSBtaW5pbXVtIHNjb3JlIHRocmVzaG9sZCAoJHttaW5pbXVtU2NvcmVUaHJlc2hvbGR9KS5gXG4gICAgKTtcbiAgICByZXR1cm4gdW5kZWZpbmVkO1xuICB9XG59XG5cbi8vIEhlbHBlciBmdW5jdGlvbiB0byBtb2NrIGZldGNoaW5nIGNhbGVuZGFyIGV2ZW50c1xuYXN5bmMgZnVuY3Rpb24gbW9ja0ZldGNoVXNlckNhbGVuZGFyRXZlbnRzKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgc3RhcnREYXRlOiBEYXRlLFxuICBlbmREYXRlOiBEYXRlXG4pOiBQcm9taXNlPENhbGVuZGFyRXZlbnRTdW1tYXJ5W10+IHtcbiAgY29uc3Qgbm93ID0gbmV3IERhdGUoKTtcbiAgY29uc3QgdG9kYXkgPSBuZXcgRGF0ZShub3cuZ2V0RnVsbFllYXIoKSwgbm93LmdldE1vbnRoKCksIG5vdy5nZXREYXRlKCkpOyAvLyBNaWRuaWdodCB0b2RheVxuXG4gIGNvbnN0IHNhbXBsZUV2ZW50czogQ2FsZW5kYXJFdmVudFN1bW1hcnlbXSA9IFtcbiAgICB7XG4gICAgICBpZDogJ2V2dDEnLFxuICAgICAgdGl0bGU6ICdQcm9qZWN0IFBob2VuaXggU3luYy1VcCcsXG4gICAgICBzdGFydFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDEpKSxcbiAgICAgIGVuZFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDEpKSxcbiAgICAgIGRlc2NyaXB0aW9uOiAnV2Vla2x5IHN5bmMgZm9yIFByb2plY3QgUGhvZW5peC4nLFxuICAgICAgYXR0ZW5kZWVzOiBbXG4gICAgICAgICdjdXJyZW50VXNlckBleGFtcGxlLmNvbScsXG4gICAgICAgICdNYXJrIEpvaG5zb24gPG1hcmsuakBleGFtcGxlLmNvbT4nLFxuICAgICAgICAndGVhbS5tZW1iZXIuamFuZUBleGFtcGxlLmNvbScsXG4gICAgICBdLFxuICAgICAgb3JnYW5pemVyOiAnbWFyay5qQGV4YW1wbGUuY29tJyxcbiAgICB9LFxuICAgIHtcbiAgICAgIGlkOiAnZXZ0MicsXG4gICAgICB0aXRsZTogJ01hcmtldGluZyBTdHJhdGVneSBNZWV0aW5nJyxcbiAgICAgIHN0YXJ0VGltZTogbmV3IERhdGUobmV3IERhdGUodG9kYXkpLnNldERhdGUodG9kYXkuZ2V0RGF0ZSgpICsgMikpLFxuICAgICAgZW5kVGltZTogbmV3IERhdGUobmV3IERhdGUodG9kYXkpLnNldERhdGUodG9kYXkuZ2V0RGF0ZSgpICsgMikpLFxuICAgICAgZGVzY3JpcHRpb246ICdEaXNjdXNzIFEzIG1hcmtldGluZyBzdHJhdGVneSB3aXRoIEFsaWNlIGFuZCB0aGUgdGVhbS4nLFxuICAgICAgYXR0ZW5kZWVzOiBbXG4gICAgICAgICdjdXJyZW50VXNlckBleGFtcGxlLmNvbScsXG4gICAgICAgICdBbGljZSBXb25kZXJsYW5kIDxhbGljZS53QGV4YW1wbGUuY29tPicsXG4gICAgICAgICdtYXJrZXRpbmdfbGVhZEBleGFtcGxlLmNvbScsXG4gICAgICAgICdCb2IgKEd1ZXN0KScsXG4gICAgICBdLFxuICAgICAgbG9jYXRpb246ICdDb25mZXJlbmNlIFJvb20gQicsXG4gICAgICBvcmdhbml6ZXI6ICdtYXJrZXRpbmdfbGVhZEBleGFtcGxlLmNvbScsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ2V2dDMnLFxuICAgICAgdGl0bGU6ICcxOjEgd2l0aCBTYXJhaCBNaWxsZXInLCAvLyBNb3JlIHNwZWNpZmljIHRpdGxlXG4gICAgICBzdGFydFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDMpKSxcbiAgICAgIGVuZFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDMpKSxcbiAgICAgIGF0dGVuZGVlczogWydjdXJyZW50VXNlckBleGFtcGxlLmNvbScsICdTYXJhaCBNaWxsZXIgPHNhcmFobUBjb3JwLmNvbT4nXSwgLy8gU3BlY2lmaWMgbWFuYWdlciBuYW1lXG4gICAgICBvcmdhbml6ZXI6ICdzYXJhaG1AY29ycC5jb20nLFxuICAgIH0sXG4gICAge1xuICAgICAgaWQ6ICdldnQ0JyxcbiAgICAgIHRpdGxlOiAnVGVhbSBMdW5jaCcsXG4gICAgICBzdGFydFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDcpKSxcbiAgICAgIGVuZFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDcpKSxcbiAgICAgIGRlc2NyaXB0aW9uOiAnQ2FzdWFsIHRlYW0gbHVuY2ggYXQgVGhlIEVhdGVyeS4nLFxuICAgICAgYXR0ZW5kZWVzOiBbXG4gICAgICAgICdjdXJyZW50VXNlckBleGFtcGxlLmNvbScsXG4gICAgICAgICdNYXJrIEpvaG5zb24gPG1hcmsuakBleGFtcGxlLmNvbT4nLFxuICAgICAgICAndGVhbS5tZW1iZXIuamFuZUBleGFtcGxlLmNvbScsXG4gICAgICAgICdBbGljZSBXb25kZXJsYW5kIDxhbGljZS53QGV4YW1wbGUuY29tPicsXG4gICAgICBdLFxuICAgICAgbG9jYXRpb246ICdUaGUgRWF0ZXJ5JyxcbiAgICAgIG9yZ2FuaXplcjogJ2N1cnJlbnRVc2VyQGV4YW1wbGUuY29tJyxcbiAgICB9LFxuICAgIHtcbiAgICAgIGlkOiAnZXZ0NScsXG4gICAgICB0aXRsZTogJ0J1ZGdldCBSZXZpZXcgUTInLFxuICAgICAgc3RhcnRUaW1lOiBuZXcgRGF0ZShuZXcgRGF0ZSh0b2RheSkuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgLSA3KSksXG4gICAgICBlbmRUaW1lOiBuZXcgRGF0ZShuZXcgRGF0ZSh0b2RheSkuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgLSA3KSksXG4gICAgICBkZXNjcmlwdGlvbjogJ0ZpbmFsIHJldmlldyBvZiBRMiBidWRnZXQuJyxcbiAgICAgIGF0dGVuZGVlczogW1xuICAgICAgICAnY3VycmVudFVzZXJAZXhhbXBsZS5jb20nLFxuICAgICAgICAnZmluYW5jZV9kZXB0QGV4YW1wbGUuY29tJyxcbiAgICAgICAgJ1NhcmFoIE1pbGxlciA8c2FyYWhtQGNvcnAuY29tPicsXG4gICAgICBdLFxuICAgICAgb3JnYW5pemVyOiAnZmluYW5jZV9kZXB0QGV4YW1wbGUuY29tJyxcbiAgICB9LFxuICAgIHtcbiAgICAgIGlkOiAnZXZ0NicsXG4gICAgICB0aXRsZTogJ1Byb2plY3QgUGhvZW5peCAtIENyaXRpY2FsIFBhdGggRGlzY3Vzc2lvbicsXG4gICAgICBzdGFydFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDEpKSxcbiAgICAgIGVuZFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDEpKSxcbiAgICAgIGRlc2NyaXB0aW9uOiAnVXJnZW50IGRpc2N1c3Npb24gb24gUHJvamVjdCBQaG9lbml4IGJsb2NrZXJzIHdpdGggTWFyay4nLFxuICAgICAgYXR0ZW5kZWVzOiBbXG4gICAgICAgICdjdXJyZW50VXNlckBleGFtcGxlLmNvbScsXG4gICAgICAgICdNYXJrIEpvaG5zb24gPG1hcmsuakBleGFtcGxlLmNvbT4nLFxuICAgICAgICAnY3RvQGV4YW1wbGUuY29tJyxcbiAgICAgIF0sXG4gICAgICBvcmdhbml6ZXI6ICdjdG9AZXhhbXBsZS5jb20nLFxuICAgIH0sXG4gICAge1xuICAgICAgLy8gTmV3IGV2ZW50IGZvciBhdHRlbmRlZSBtYXRjaGluZ1xuICAgICAgaWQ6ICdldnQ3JyxcbiAgICAgIHRpdGxlOiAnUGxhbm5pbmcgU2Vzc2lvbicsXG4gICAgICBzdGFydFRpbWU6IG5ldyBEYXRlKG5ldyBEYXRlKHRvZGF5KS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSArIDQpKSwgLy8gNCBkYXlzIGZyb20gbm93IDEwIEFNXG4gICAgICBlbmRUaW1lOiBuZXcgRGF0ZShuZXcgRGF0ZSh0b2RheSkuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgKyA0KSksIC8vIDQgZGF5cyBmcm9tIG5vdyAxMiBQTVxuICAgICAgZGVzY3JpcHRpb246ICdHZW5lcmFsIHBsYW5uaW5nIG1lZXRpbmcuJyxcbiAgICAgIGF0dGVuZGVlczogW1xuICAgICAgICAnY3VycmVudFVzZXJAZXhhbXBsZS5jb20nLFxuICAgICAgICAnQWxpY2UgV29uZGVybGFuZCA8YWxpY2Uud0BleGFtcGxlLmNvbT4nLFxuICAgICAgICAnQm9iIFRoZSBCdWlsZGVyIDxib2JAYnVpbGQuaXQ+JyxcbiAgICAgICAgJ0NoYXJsaWUgPGNoYXJsaWUuZG9lQGVtYWlsLmNvbT4nLFxuICAgICAgXSxcbiAgICAgIG9yZ2FuaXplcjogJ2N1cnJlbnRVc2VyQGV4YW1wbGUuY29tJyxcbiAgICB9LFxuICBdO1xuXG4gIC8vIEFkanVzdCBmaXhlZCB0aW1lcyBmb3Igc2FtcGxlIGV2ZW50cyB0byBiZSByZWxhdGl2ZSB0byAndG9kYXknIGZvciBjb25zaXN0ZW50IHRlc3RpbmdcbiAgc2FtcGxlRXZlbnRzLmZvckVhY2goKGV2ZW50KSA9PiB7XG4gICAgaWYgKGV2ZW50LmlkID09PSAnZXZ0MScpIHtcbiAgICAgIGV2ZW50LnN0YXJ0VGltZS5zZXRIb3Vycyg5LCAwLCAwLCAwKTtcbiAgICAgIGV2ZW50LmVuZFRpbWUuc2V0SG91cnMoMTAsIDAsIDAsIDApOyAvLyBUb21vcnJvdyA5IEFNXG4gICAgfSBlbHNlIGlmIChldmVudC5pZCA9PT0gJ2V2dDInKSB7XG4gICAgICBldmVudC5zdGFydFRpbWUuc2V0SG91cnMoMTQsIDAsIDAsIDApO1xuICAgICAgZXZlbnQuZW5kVGltZS5zZXRIb3VycygxNSwgMCwgMCwgMCk7IC8vIERheSBhZnRlciB0b21vcnJvdyAyIFBNXG4gICAgfSBlbHNlIGlmIChldmVudC5pZCA9PT0gJ2V2dDMnKSB7XG4gICAgICBldmVudC5zdGFydFRpbWUuc2V0SG91cnMoMTEsIDAsIDAsIDApO1xuICAgICAgZXZlbnQuZW5kVGltZS5zZXRIb3VycygxMSwgMzAsIDAsIDApOyAvLyAzIGRheXMgZnJvbSBub3cgMTEgQU1cbiAgICB9IGVsc2UgaWYgKGV2ZW50LmlkID09PSAnZXZ0NCcpIHtcbiAgICAgIGV2ZW50LnN0YXJ0VGltZS5zZXRIb3VycygxMiwgMCwgMCwgMCk7XG4gICAgICBldmVudC5lbmRUaW1lLnNldEhvdXJzKDEzLCAwLCAwLCAwKTsgLy8gTmV4dCB3ZWVrIDEyIFBNXG4gICAgfSBlbHNlIGlmIChldmVudC5pZCA9PT0gJ2V2dDUnKSB7XG4gICAgICBldmVudC5zdGFydFRpbWUuc2V0SG91cnMoMTUsIDAsIDAsIDApO1xuICAgICAgZXZlbnQuZW5kVGltZS5zZXRIb3VycygxNiwgMCwgMCwgMCk7IC8vIExhc3Qgd2VlayAzIFBNXG4gICAgfSBlbHNlIGlmIChldmVudC5pZCA9PT0gJ2V2dDYnKSB7XG4gICAgICBldmVudC5zdGFydFRpbWUuc2V0SG91cnMoMTQsIDAsIDAsIDApO1xuICAgICAgZXZlbnQuZW5kVGltZS5zZXRIb3VycygxNSwgMCwgMCwgMCk7IC8vIFRvbW9ycm93IDIgUE1cbiAgICB9IGVsc2UgaWYgKGV2ZW50LmlkID09PSAnZXZ0NycpIHtcbiAgICAgIGV2ZW50LnN0YXJ0VGltZS5zZXRIb3VycygxMCwgMCwgMCwgMCk7XG4gICAgICBldmVudC5lbmRUaW1lLnNldEhvdXJzKDEyLCAwLCAwLCAwKTsgLy8gNCBkYXlzIGZyb20gbm93IDEwIEFNXG4gICAgfVxuICB9KTtcblxuICBjb25zb2xlLmxvZyhcbiAgICBgW21vY2tGZXRjaFVzZXJDYWxlbmRhckV2ZW50c10gTW9jayBVc2VySUQ6ICR7dXNlcklkfS4gRmlsdGVyaW5nIGV2ZW50cyBiZXR3ZWVuICR7c3RhcnREYXRlLnRvSVNPU3RyaW5nKCl9IGFuZCAke2VuZERhdGUudG9JU09TdHJpbmcoKX1gXG4gICk7XG5cbiAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBzYW1wbGVFdmVudHMuZmlsdGVyKChldmVudCkgPT4ge1xuICAgIHJldHVybiBldmVudC5zdGFydFRpbWUgPj0gc3RhcnREYXRlICYmIGV2ZW50LnN0YXJ0VGltZSA8PSBlbmREYXRlO1xuICB9KTtcblxuICBjb25zb2xlLmxvZyhcbiAgICBgW21vY2tGZXRjaFVzZXJDYWxlbmRhckV2ZW50c10gUmV0dXJuaW5nICR7ZmlsdGVyZWRFdmVudHMubGVuZ3RofSBtb2NrIGV2ZW50cyBhZnRlciBmaWx0ZXJpbmcuYFxuICApO1xuICByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKGZpbHRlcmVkRXZlbnRzKTtcbn1cbiJdfQ==