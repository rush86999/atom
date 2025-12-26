// Type declarations for external modules without types

declare module 'intuit-oauth' {
    interface OAuthClientConfig {
        clientId: string | undefined;
        clientSecret: string | undefined;
        environment: string | undefined;
        redirectUri: string | undefined;
    }

    interface Token {
        access_token: string;
        refresh_token: string;
        token_type: string;
        expires_in: number;
        x_refresh_token_expires_in: number;
        realmId?: string;
    }

    interface AuthResponse {
        getJson(): Token;
        getToken(): Token;
    }

    class OAuthClient {
        static scopes: Record<string, string>;
        constructor(config: OAuthClientConfig);
        authorizeUri(params: { scope: string | string[]; state: string }): string;
        createToken(url: string): Promise<AuthResponse>;
        refresh(): Promise<AuthResponse>;
        revoke(params?: { access_token?: string; refresh_token?: string }): Promise<AuthResponse>;
        setToken(token: Token): void;
        getToken(): Token;
        isAccessTokenValid(): boolean;
    }

    export default OAuthClient;
}

declare module 'helmet' {
    import { RequestHandler } from 'express';
    function helmet(options?: any): RequestHandler;
    export = helmet;
}

declare module 'morgan' {
    import { RequestHandler } from 'express';
    function morgan(format: string, options?: any): RequestHandler;
    export = morgan;
}

// Web Speech API types
interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
    resultIndex: number;
}

interface SpeechRecognitionResultList {
    length: number;
    item(index: number): SpeechRecognitionResult;
    [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
    length: number;
    item(index: number): SpeechRecognitionAlternative;
    [index: number]: SpeechRecognitionAlternative;
    isFinal: boolean;
}

interface SpeechRecognitionAlternative {
    transcript: string;
    confidence: number;
}

interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    maxAlternatives: number;
    onaudioend: ((this: SpeechRecognition, ev: Event) => any) | null;
    onaudiostart: ((this: SpeechRecognition, ev: Event) => any) | null;
    onend: ((this: SpeechRecognition, ev: Event) => any) | null;
    onerror: ((this: SpeechRecognition, ev: Event) => any) | null;
    onnomatch: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => any) | null;
    onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => any) | null;
    onsoundend: ((this: SpeechRecognition, ev: Event) => any) | null;
    onsoundstart: ((this: SpeechRecognition, ev: Event) => any) | null;
    onspeechend: ((this: SpeechRecognition, ev: Event) => any) | null;
    onspeechstart: ((this: SpeechRecognition, ev: Event) => any) | null;
    onstart: ((this: SpeechRecognition, ev: Event) => any) | null;
    start(): void;
    stop(): void;
    abort(): void;
}

declare var SpeechRecognition: {
    prototype: SpeechRecognition;
    new(): SpeechRecognition;
};

declare module 'mermaid' {
    const mermaid: any;
    export default mermaid;
}

declare module 'formidable' {
    const formidable: any;
    export default formidable;
}
