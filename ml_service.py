import mysql.connector
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from dotenv import load_dotenv

load_dotenv()

# ---------- DATABASE FORBINDELSE ----------

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# ---------- HENT DATA FRA DATABASE ----------

def load_data():
    conn = get_connection()
    query = """
        SELECT 
            power_kw,
            voltage,
            current_a,
            temperature,
            CASE 
                WHEN error_code IS NULL THEN 'NORMAL'
                ELSE error_code
            END as label
        FROM telemetry_reading
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# ---------- TRÆN MODEL ----------

def train_model():
    print("Henter data fra databasen...")
    df = load_data()
    print(f"✅ {len(df)} rækker hentet")

    # Features og labels
    X = df[["power_kw", "voltage", "current_a", "temperature"]]
    y = df["label"]

    # Split data i træning og test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"✅ Træningsdata: {len(X_train)} rækker")
    print(f"✅ Testdata: {len(X_test)} rækker")

    # Træn Random Forest model
    print("Træner Random Forest model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    print("✅ Model trænet!")

    # Evaluer modellen
    y_pred = model.predict(X_test)
    print("\n📊 Model performance:")
    print(classification_report(y_test, y_pred))

    # Feature importance
    feature_names = ["power_kw", "voltage", "current_a", "temperature"]
    importances = model.feature_importances_
    print("📊 Feature importance (hvilke målinger betyder mest):")
    for name, importance in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
        print(f"  {name}: {importance:.3f}")

    return model

# ---------- FORUDSIG FEJL ----------

def predict(model, power_kw, voltage, current_a, temperature):
    """
    Forudsiger om en ladestander er ved at fejle
    baseret på aktuelle målinger
    """
    input_data = pd.DataFrame([[power_kw, voltage, current_a, temperature]],
                               columns=["power_kw", "voltage", "current_a", "temperature"])
    
    prediction = model.predict(input_data)[0]
    probabilities = model.predict_proba(input_data)[0]
    classes = model.classes_
    
    # Find sandsynlighed for den forudsagte klasse
    prob_dict = dict(zip(classes, probabilities))
    
    print(f"\n🔍 Forudsigelse for måling:")
    print(f"   power_kw={power_kw}, voltage={voltage}, current_a={current_a}, temperature={temperature}")
    print(f"   Forudsagt: {prediction}")
    print(f"   Sandsynligheder:")
    for label, prob in sorted(prob_dict.items(), key=lambda x: x[1], reverse=True):
        print(f"     {label}: {prob:.1%}")
    
    return prediction, prob_dict

# ---------- KØR ----------

if __name__ == "__main__":
    # Træn modellen
    model = train_model()

    print("\n" + "="*50)
    print("🧪 Test forudsigelser på nye målinger:")
    print("="*50)

    # Test 1 — Normal måling
    predict(model, power_kw=11.0, voltage=230.0, current_a=20.0, temperature=45.0)

    # Test 2 — Høj temperatur
    predict(model, power_kw=2.0, voltage=230.0, current_a=3.0, temperature=92.0)

    # Test 3 — Ingen strøm
    predict(model, power_kw=0.0, voltage=120.0, current_a=0.0, temperature=25.0)

    # Test 4 — Ledningsskade
    predict(model, power_kw=0.0, voltage=230.0, current_a=0.0, temperature=35.0)
    