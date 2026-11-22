# k6 summary

scenario: aoi_summary

- http_req_sending: p(95)=0.436, p(99)=0.523, avg=0.105, min=0.032, med=0.058, max=0.544, p(90)=0.196
- http_req_duration: min=165.777, med=188.919, max=244.416, p(90)=216.009, p(95)=217.716, p(99)=239.076, avg=191.730
- http_req_duration{expected_response:true}: p(90)=216.009, p(95)=217.716, p(99)=239.076, avg=191.730, min=165.777, med=188.919, max=244.416
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_connecting: p(95)=0.004, p(99)=0.057, avg=0.004, min=0.000, med=0.000, max=0.071, p(90)=0.000
- iterations: count=20.000, rate=2.546
- http_req_waiting: p(95)=217.261, p(99)=238.763, avg=191.325, min=165.151, med=188.378, max=244.139, p(90)=215.259
- http_req_receiving: max=0.741, p(90)=0.589, p(95)=0.723, p(99)=0.737, avg=0.300, min=0.114, med=0.213
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_blocked: p(99)=0.086, avg=0.016, min=0.007, med=0.011, max=0.102, p(90)=0.016, p(95)=0.024
