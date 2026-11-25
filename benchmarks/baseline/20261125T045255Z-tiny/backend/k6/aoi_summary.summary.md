# k6 summary

scenario: aoi_summary

- http_req_waiting: p(99)=54.855, avg=26.083, min=9.762, med=27.392, max=55.937, p(90)=33.874, p(95)=38.483
- http_req_failed: rate=0.000
- http_req_receiving: avg=0.093, min=0.032, med=0.077, max=0.443, p(90)=0.131, p(95)=0.167, p(99)=0.418
- iterations: count=90.000, rate=8.804
- http_req_connecting: med=0.000, max=0.091, p(90)=0.000, p(95)=0.000, p(99)=0.091, avg=0.002, min=0.000
- http_req_sending: p(90)=0.071, p(95)=0.087, p(99)=0.147, avg=0.055, min=0.011, med=0.053, max=0.149
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_duration{expected_response:true}: max=56.429, p(90)=33.988, p(95)=38.604, p(99)=55.316, avg=26.231, min=9.842, med=27.541
- http_req_blocked: min=0.002, med=0.011, max=0.133, p(90)=0.016, p(95)=0.021, p(99)=0.132, avg=0.014
- http_req_duration: p(99)=55.316, avg=26.231, min=9.842, med=27.541, max=56.429, p(90)=33.988, p(95)=38.604
- vus: min=2.000, max=2.000
