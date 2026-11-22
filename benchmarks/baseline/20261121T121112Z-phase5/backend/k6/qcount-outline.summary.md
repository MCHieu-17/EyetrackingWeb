# k6 summary

scenario: outline

- http_req_blocked: avg=0.019, min=0.010, med=0.011, max=0.155, p(90)=0.018, p(95)=0.031, p(99)=0.130
- http_req_duration: avg=11.485, min=6.410, med=11.696, max=15.280, p(90)=13.727, p(95)=14.288, p(99)=15.081
- http_req_connecting: min=0.000, med=0.000, max=0.112, p(90)=0.000, p(95)=0.006, p(99)=0.091, avg=0.006
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: avg=11.264, min=6.304, med=11.494, max=15.095, p(90)=13.019, p(95)=13.986, p(99)=14.873
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.706
- http_req_duration{expected_response:true}: avg=11.485, min=6.410, med=11.696, max=15.280, p(90)=13.727, p(95)=14.288, p(99)=15.081
- http_req_sending: avg=0.045, min=0.027, med=0.043, max=0.062, p(90)=0.053, p(95)=0.055, p(99)=0.060
- http_req_receiving: max=0.709, p(90)=0.244, p(95)=0.278, p(99)=0.623, avg=0.177, min=0.054, med=0.139
