# k6 summary

scenario: course_visits

- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: avg=33.949, min=15.303, med=31.869, max=52.006, p(90)=49.597, p(95)=50.474, p(99)=51.700
- http_req_connecting: p(99)=0.074, avg=0.005, min=0.000, med=0.000, max=0.091, p(90)=0.000, p(95)=0.005
- http_req_waiting: max=51.629, p(90)=49.198, p(95)=50.262, p(99)=51.355, avg=33.726, min=15.173, med=31.730
- http_req_receiving: p(90)=0.322, p(95)=0.339, p(99)=0.369, avg=0.180, min=0.075, med=0.154, max=0.376
- http_req_blocked: min=0.004, med=0.011, max=0.124, p(90)=0.016, p(95)=0.026, p(99)=0.104, avg=0.017
- iterations: count=20.000, rate=4.258
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_sending: avg=0.043, min=0.014, med=0.042, max=0.066, p(90)=0.054, p(95)=0.058, p(99)=0.064
- http_req_duration: med=31.869, max=52.006, p(90)=49.597, p(95)=50.474, p(99)=51.700, avg=33.949, min=15.303
- http_req_failed: rate=0.000
