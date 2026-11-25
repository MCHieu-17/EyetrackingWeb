# k6 summary

scenario: replay

- vus: min=2.000, max=2.000
- http_req_duration: p(99)=33.798, avg=9.823, min=2.656, med=9.636, max=35.446, p(90)=12.881, p(95)=13.974
- http_req_waiting: min=2.583, med=9.487, max=34.410, p(90)=12.619, p(95)=13.647, p(99)=32.280, avg=9.606
- http_req_receiving: p(90)=0.338, p(95)=0.425, p(99)=1.004, avg=0.177, min=0.025, med=0.123, max=1.507
- http_req_blocked: avg=0.013, min=0.002, med=0.011, max=0.114, p(90)=0.014, p(95)=0.016, p(99)=0.113
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_failed: rate=0.000
- http_req_connecting: p(90)=0.000, p(95)=0.000, p(99)=0.083, avg=0.002, min=0.000, med=0.000, max=0.084
- http_req_sending: max=0.065, p(90)=0.049, p(95)=0.055, p(99)=0.062, avg=0.041, min=0.006, med=0.042
- iterations: count=96.000, rate=9.488
- http_req_duration{expected_response:true}: avg=9.823, min=2.656, med=9.636, max=35.446, p(90)=12.881, p(95)=13.974, p(99)=33.798
