"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.frontendConfig = void 0;
const thirdpartyemailpassword_1 = __importDefault(require("supertokens-auth-react/recipe/thirdpartyemailpassword"));
const session_1 = __importDefault(require("supertokens-auth-react/recipe/session"));
const appInfo_1 = require("./appInfo");
const router_1 = __importDefault(require("next/router"));
const frontendConfig = () => {
    return {
        appInfo: appInfo_1.appInfo,
        recipeList: [
            thirdpartyemailpassword_1.default.init({
                signInAndUpFeature: {
                    providers: [
                        thirdpartyemailpassword_1.default.Google.init(),
                        thirdpartyemailpassword_1.default.Facebook.init(),
                        thirdpartyemailpassword_1.default.Github.init(),
                        thirdpartyemailpassword_1.default.Apple.init(),
                    ],
                },
            }),
            session_1.default.init(),
        ],
        windowHandler: (oI) => {
            return {
                ...oI,
                location: {
                    ...oI.location,
                    setHref: (href) => {
                        router_1.default.push(href);
                    },
                },
            };
        },
    };
};
exports.frontendConfig = frontendConfig;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZnJvbnRlbmRDb25maWcuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJmcm9udGVuZENvbmZpZy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSxvSEFBaUc7QUFDakcsb0ZBQWlFO0FBQ2pFLHVDQUFvQztBQUNwQyx5REFBaUM7QUFFMUIsTUFBTSxjQUFjLEdBQUcsR0FBRyxFQUFFO0lBQ2pDLE9BQU87UUFDTCxPQUFPLEVBQVAsaUJBQU87UUFDUCxVQUFVLEVBQUU7WUFDVixpQ0FBNEIsQ0FBQyxJQUFJLENBQUM7Z0JBQ2hDLGtCQUFrQixFQUFFO29CQUNsQixTQUFTLEVBQUU7d0JBQ1QsaUNBQTRCLENBQUMsTUFBTSxDQUFDLElBQUksRUFBRTt3QkFDMUMsaUNBQTRCLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRTt3QkFDNUMsaUNBQTRCLENBQUMsTUFBTSxDQUFDLElBQUksRUFBRTt3QkFDMUMsaUNBQTRCLENBQUMsS0FBSyxDQUFDLElBQUksRUFBRTtxQkFDMUM7aUJBQ0Y7YUFDRixDQUFDO1lBQ0YsaUJBQVksQ0FBQyxJQUFJLEVBQUU7U0FDcEI7UUFDRCxhQUFhLEVBQUUsQ0FBQyxFQUFPLEVBQUUsRUFBRTtZQUN6QixPQUFPO2dCQUNMLEdBQUcsRUFBRTtnQkFDTCxRQUFRLEVBQUU7b0JBQ1IsR0FBRyxFQUFFLENBQUMsUUFBUTtvQkFDZCxPQUFPLEVBQUUsQ0FBQyxJQUFZLEVBQUUsRUFBRTt3QkFDeEIsZ0JBQU0sQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUM7b0JBQ3BCLENBQUM7aUJBQ0Y7YUFDRixDQUFDO1FBQ0osQ0FBQztLQUNGLENBQUM7QUFDSixDQUFDLENBQUM7QUE1QlcsUUFBQSxjQUFjLGtCQTRCekIiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgVGhpcmRQYXJ0eUVtYWlsUGFzc3dvcmRSZWFjdCBmcm9tICdzdXBlcnRva2Vucy1hdXRoLXJlYWN0L3JlY2lwZS90aGlyZHBhcnR5ZW1haWxwYXNzd29yZCc7XG5pbXBvcnQgU2Vzc2lvblJlYWN0IGZyb20gJ3N1cGVydG9rZW5zLWF1dGgtcmVhY3QvcmVjaXBlL3Nlc3Npb24nO1xuaW1wb3J0IHsgYXBwSW5mbyB9IGZyb20gJy4vYXBwSW5mbyc7XG5pbXBvcnQgUm91dGVyIGZyb20gJ25leHQvcm91dGVyJztcblxuZXhwb3J0IGNvbnN0IGZyb250ZW5kQ29uZmlnID0gKCkgPT4ge1xuICByZXR1cm4ge1xuICAgIGFwcEluZm8sXG4gICAgcmVjaXBlTGlzdDogW1xuICAgICAgVGhpcmRQYXJ0eUVtYWlsUGFzc3dvcmRSZWFjdC5pbml0KHtcbiAgICAgICAgc2lnbkluQW5kVXBGZWF0dXJlOiB7XG4gICAgICAgICAgcHJvdmlkZXJzOiBbXG4gICAgICAgICAgICBUaGlyZFBhcnR5RW1haWxQYXNzd29yZFJlYWN0Lkdvb2dsZS5pbml0KCksXG4gICAgICAgICAgICBUaGlyZFBhcnR5RW1haWxQYXNzd29yZFJlYWN0LkZhY2Vib29rLmluaXQoKSxcbiAgICAgICAgICAgIFRoaXJkUGFydHlFbWFpbFBhc3N3b3JkUmVhY3QuR2l0aHViLmluaXQoKSxcbiAgICAgICAgICAgIFRoaXJkUGFydHlFbWFpbFBhc3N3b3JkUmVhY3QuQXBwbGUuaW5pdCgpLFxuICAgICAgICAgIF0sXG4gICAgICAgIH0sXG4gICAgICB9KSxcbiAgICAgIFNlc3Npb25SZWFjdC5pbml0KCksXG4gICAgXSxcbiAgICB3aW5kb3dIYW5kbGVyOiAob0k6IGFueSkgPT4ge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgLi4ub0ksXG4gICAgICAgIGxvY2F0aW9uOiB7XG4gICAgICAgICAgLi4ub0kubG9jYXRpb24sXG4gICAgICAgICAgc2V0SHJlZjogKGhyZWY6IHN0cmluZykgPT4ge1xuICAgICAgICAgICAgUm91dGVyLnB1c2goaHJlZik7XG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfSxcbiAgfTtcbn07XG4iXX0=