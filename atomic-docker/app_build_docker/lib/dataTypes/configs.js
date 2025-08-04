"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.googleConfig = void 0;
const react_native_1 = require("react-native");
// android redirect: com.googleusercontent.apps.159344105155-uh4g7h127eg5r7nv0hm333ftk0nehpaq:/oauth2redirect/google
exports.googleConfig = react_native_1.Platform.OS === 'android'
    ? {
        issuer: 'https://accounts.google.com',
        clientId: '159344105155-rmomk5vti4hbr0euohtdklltqh7432qk.apps.googleusercontent.com',
        redirectUrl: 'com.googleusercontent.apps.159344105155-rmomk5vti4hbr0euohtdklltqh7432qk:/oauth2redirect',
        scopes: [
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/contacts.readonly',
        ],
    }
    : {
        issuer: 'https://accounts.google.com',
        clientId: '159344105155-2a6grpvmkki1dkkche8o7bishssrd1qb.apps.googleusercontent.com',
        redirectUrl: 'com.googleusercontent.apps.159344105155-2a6grpvmkki1dkkche8o7bishssrd1qb:/oauth2redirect/google',
        scopes: [
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/contacts.readonly',
        ],
    };
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29uZmlncy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNvbmZpZ3MudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsK0NBQXdDO0FBRXhDLG9IQUFvSDtBQUN2RyxRQUFBLFlBQVksR0FDdkIsdUJBQVEsQ0FBQyxFQUFFLEtBQUssU0FBUztJQUN2QixDQUFDLENBQUM7UUFDRSxNQUFNLEVBQUUsNkJBQTZCO1FBQ3JDLFFBQVEsRUFDTiwwRUFBMEU7UUFDNUUsV0FBVyxFQUNULDBGQUEwRjtRQUM1RixNQUFNLEVBQUU7WUFDTixtREFBbUQ7WUFDbkQsaURBQWlEO1lBQ2pELG1EQUFtRDtTQUNwRDtLQUNGO0lBQ0gsQ0FBQyxDQUFDO1FBQ0UsTUFBTSxFQUFFLDZCQUE2QjtRQUNyQyxRQUFRLEVBQ04sMEVBQTBFO1FBQzVFLFdBQVcsRUFDVCxpR0FBaUc7UUFDbkcsTUFBTSxFQUFFO1lBQ04sbURBQW1EO1lBQ25ELGlEQUFpRDtZQUNqRCxtREFBbUQ7U0FDcEQ7S0FDRixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUGxhdGZvcm0gfSBmcm9tICdyZWFjdC1uYXRpdmUnO1xuXG4vLyBhbmRyb2lkIHJlZGlyZWN0OiBjb20uZ29vZ2xldXNlcmNvbnRlbnQuYXBwcy4xNTkzNDQxMDUxNTUtdWg0ZzdoMTI3ZWc1cjdudjBobTMzM2Z0azBuZWhwYXE6L29hdXRoMnJlZGlyZWN0L2dvb2dsZVxuZXhwb3J0IGNvbnN0IGdvb2dsZUNvbmZpZyA9XG4gIFBsYXRmb3JtLk9TID09PSAnYW5kcm9pZCdcbiAgICA/IHtcbiAgICAgICAgaXNzdWVyOiAnaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tJyxcbiAgICAgICAgY2xpZW50SWQ6XG4gICAgICAgICAgJzE1OTM0NDEwNTE1NS1ybW9tazV2dGk0aGJyMGV1b2h0ZGtsbHRxaDc0MzJxay5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbScsXG4gICAgICAgIHJlZGlyZWN0VXJsOlxuICAgICAgICAgICdjb20uZ29vZ2xldXNlcmNvbnRlbnQuYXBwcy4xNTkzNDQxMDUxNTUtcm1vbWs1dnRpNGhicjBldW9odGRrbGx0cWg3NDMycWs6L29hdXRoMnJlZGlyZWN0JyxcbiAgICAgICAgc2NvcGVzOiBbXG4gICAgICAgICAgJ2h0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL2F1dGgvY2FsZW5kYXIucmVhZG9ubHknLFxuICAgICAgICAgICdodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9hdXRoL2NhbGVuZGFyLmV2ZW50cycsXG4gICAgICAgICAgJ2h0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL2F1dGgvY29udGFjdHMucmVhZG9ubHknLFxuICAgICAgICBdLFxuICAgICAgfVxuICAgIDoge1xuICAgICAgICBpc3N1ZXI6ICdodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20nLFxuICAgICAgICBjbGllbnRJZDpcbiAgICAgICAgICAnMTU5MzQ0MTA1MTU1LTJhNmdycHZta2tpMWRra2NoZThvN2Jpc2hzc3JkMXFiLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tJyxcbiAgICAgICAgcmVkaXJlY3RVcmw6XG4gICAgICAgICAgJ2NvbS5nb29nbGV1c2VyY29udGVudC5hcHBzLjE1OTM0NDEwNTE1NS0yYTZncnB2bWtraTFka2tjaGU4bzdiaXNoc3NyZDFxYjovb2F1dGgycmVkaXJlY3QvZ29vZ2xlJyxcbiAgICAgICAgc2NvcGVzOiBbXG4gICAgICAgICAgJ2h0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL2F1dGgvY2FsZW5kYXIucmVhZG9ubHknLFxuICAgICAgICAgICdodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9hdXRoL2NhbGVuZGFyLmV2ZW50cycsXG4gICAgICAgICAgJ2h0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL2F1dGgvY29udGFjdHMucmVhZG9ubHknLFxuICAgICAgICBdLFxuICAgICAgfTtcbiJdfQ==