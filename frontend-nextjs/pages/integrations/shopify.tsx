import React, { useState, useEffect, useCallback } from "react";
import { NextPage } from "next";
import Head from "next/head";
import { useRouter } from "next/router";

const ShopifyPage: NextPage = () => {
    const router = useRouter();
    const { connected, shop } = router.query as { connected?: string; shop?: string };
    const [isConnected, setIsConnected] = useState<boolean>(connected === "true");
    const [connectedShop, setConnectedShop] = useState<string>(shop || "");
    const [shopName, setShopName] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(true);
    const [connecting, setConnecting] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const getToken = () =>
        typeof window !== "undefined"
            ? localStorage.getItem("auth_token") || localStorage.getItem("token")
            : null;

    const checkConnection = useCallback(async () => {
        try {
            const token = getToken();
            const res = await fetch("/api/shopify/connection", {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (res.ok) {
                const data = await res.json();
                setIsConnected(data.connected === true);
                setConnectedShop(data.shop || "");
            }
        } catch (e) {
            console.error("Shopify connection check failed:", e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        checkConnection();
    }, [checkConnection]);

    const handleConnect = async () => {
        const name = shopName.trim();
        if (!name) {
            setError("Please enter your Shopify shop name (e.g. my-great-store).");
            return;
        }
        setError(null);
        setConnecting(true);
        try {
            const token = getToken();
            const res = await fetch(
                `/api/shopify/auth/url?shop=${encodeURIComponent(name)}`,
                { headers: token ? { Authorization: `Bearer ${token}` } : {} },
            );
            if (!res.ok) {
                const data = await res.json().catch((): null => null);
                throw new Error(data?.detail || "Failed to get authorization URL");
            }
            const data = await res.json();
            if (data.url) {
                window.location.href = data.url;
            } else {
                throw new Error("No authorization URL returned");
            }
        } catch (e: any) {
            setError(e?.message || "Failed to initiate Shopify connection.");
            setConnecting(false);
        }
    };

    return (
        <>
            <Head>
                <title>Shopify | ATOM</title>
            </Head>
            <div className="p-6 max-w-4xl mx-auto">
                <h1 className="text-2xl font-bold mb-1">Shopify</h1>
                <p className="text-muted-foreground mb-6">
                    Connect your Shopify store so agents can create product
                    listings and publish blog posts automatically.
                </p>

                {loading ? (
                    <div className="text-muted-foreground italic">Checking connection...</div>
                ) : isConnected ? (
                    <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                        <div className="font-semibold text-green-800">
                            Connected to {connectedShop || "your Shopify store"}
                        </div>
                        <p className="text-sm text-green-700 mt-1">
                            Agents can now create listings and blog posts. Ask your
                            assistant things like: &quot;Shopify pe naya product listing
                            banao&quot; ya &quot;Blog post likho aur publish karo&quot;.
                        </p>
                        <button
                            onClick={() => { router.push("/chat"); }}
                            className="mt-4 bg-green-600 hover:bg-green-700 text-white font-medium px-4 py-2 rounded-md"
                        >
                            Go to Chat &amp; Start
                        </button>
                    </div>
                ) : (
                    <div className="rounded-lg border border-border p-6">
                        <h2 className="text-lg font-semibold mb-3">Connect your store</h2>
                        {error && (
                            <div className="text-destructive text-sm mb-3">{error}</div>
                        )}
                        <label className="block text-sm font-medium mb-1" htmlFor="shopName">
                            Shop name
                        </label>
                        <input
                            id="shopName"
                            className="w-full max-w-sm border rounded-md px-3 py-2 mb-4 bg-background"
                            placeholder="my-great-store"
                            value={shopName}
                            onChange={(e) => setShopName(e.target.value)}
                        />
                        <br />
                        <button
                            onClick={handleConnect}
                            disabled={connecting}
                            className="bg-purple-600 hover:bg-purple-700 text-white font-medium px-4 py-2 rounded-md disabled:opacity-50"
                        >
                            {connecting ? "Redirecting to Shopify..." : "Connect Shopify"}
                        </button>
                        <p className="text-xs text-muted-foreground mt-3">
                            Requires SHOPIFY_API_KEY / SHOPIFY_API_SECRET in the backend
                            environment and write_products / write_content scopes.
                        </p>
                    </div>
                )}
            </div>
        </>
    );
};

export default ShopifyPage;