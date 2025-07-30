import Logo from "@components/Logo";
import config from "@config/config.json";
import menu from "@config/menu.json";
import social from "@config/social.json";
import Link from "next/link";
import { useRouter } from "next/router";
import React, { useState } from "react";
import {
  FaReddit,
  FaTwitter,
} from "react-icons/fa";
import { type UrlObject } from "url";

const Header = () => {
  //router
  const router = useRouter();

  // distructuring the main menu from menu object
  const { main } = menu as any;

  // states declaration
  const [navOpen, setNavOpen] = useState(false);

  // logo source
  const { logo } = config.site;
  const { enable, link } = config.nav_button;

  return (
    <header className="">
      <nav className="">
        <ul className="social-icons">
          <li>
            <Link
              href={social.twitter}
              target="_blank"
              rel="noopener noreferrer"
            >
              <FaTwitter />
            </Link>
          </li>
          <li>
            <Link
              href={social.reddit}
              target="_blank"
              rel="noopener noreferrer"
            >
              <FaReddit />
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
};

export default Header;
