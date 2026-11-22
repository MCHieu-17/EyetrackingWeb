# k6 summary

scenario: samples

- http_req_waiting: min=4.314, med=14.881, max=18.158, p(90)=17.692, p(95)=17.789, p(99)=18.084, avg=13.027
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_blocked: avg=0.041, min=0.004, med=0.011, max=0.624, p(90)=0.013, p(95)=0.044, p(99)=0.508
- http_req_receiving: p(90)=0.198, p(95)=0.248, p(99)=0.730, avg=0.159, min=0.039, med=0.120, max=0.850
- http_req_sending: p(90)=0.075, p(95)=0.092, p(99)=0.168, avg=0.051, min=0.016, med=0.043, max=0.187
- http_req_duration: p(90)=18.010, p(95)=18.404, p(99)=18.529, avg=13.238, min=4.379, med=15.061, max=18.560
- iterations: count=20.000, rate=4.666
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: min=4.379, med=15.061, max=18.560, p(90)=18.010, p(95)=18.404, p(99)=18.529, avg=13.238
- http_req_connecting: p(99)=0.433, avg=0.027, min=0.000, med=0.000, max=0.534, p(90)=0.000, p(95)=0.027
