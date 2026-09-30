import React from 'react';
import { Link } from 'react-router-dom';
import StorefrontIcon from '@material-ui/icons/Storefront';
import ShoppingCartIcon from '@material-ui/icons/ShoppingCart';
import StorageIcon from '@material-ui/icons/Storage';
import LocalShippingIcon from '@material-ui/icons/LocalShipping';
import AccountCircleIcon from '@material-ui/icons/AccountCircle';
import EmailIcon from '@material-ui/icons/Email';
import './Home.css';

const Home = () => {
  return (
    <div className="home-container">
      <header className="home-header">
        <h1>Welcome to the E-commerce App</h1>
        <p>Choose any of the following options</p>
      </header>
      <main className="home-content">
        <section className="microservice-section">
          <StorefrontIcon className="card-icon" />
          <h2>Product Catalog</h2>
          <p>Browse our product catalog.</p>
          <Link to="/products" className="btn">View Products</Link>
        </section>
        <section className="microservice-section">
          <ShoppingCartIcon className="card-icon" />
          <h2>Order Management</h2>
          <p>Place and track your orders.</p>
          <Link to="/orders" className="btn">Manage Orders</Link>
        </section>
        <section className="microservice-section">
          <StorageIcon className="card-icon" />
          <h2>Inventory Management</h2>
          <p>Check stock levels and availability.</p>
          <Link to="/inventory" className="btn">View Inventory</Link>
        </section>
        <section className="microservice-section">
          <LocalShippingIcon className="card-icon" />
          <h2>Shipping</h2>
          <p>Learn about our shipping services.</p>
          <Link to="/shipping" className="btn">Shipping Options</Link>
        </section>
        <section className="microservice-section">
          <AccountCircleIcon className="card-icon" />
          <h2>Profile Management</h2>
          <p>Manage your profile.</p>
          <Link to="/profile" className="btn">Manage Profile</Link>
        </section>
        <section className="microservice-section">
          <EmailIcon className="card-icon" />
          <h2>Contact Us</h2>
          <p>Get in touch with our support team.</p>
          <Link to="/contact" className="btn">Contact Support</Link>
        </section>
      </main>
    </div>
  );
};

export default Home;