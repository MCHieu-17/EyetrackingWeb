# k6 summary

scenario: aoi_summary

- http_req_blocked: avg=0.017, min=0.009, med=0.011, max=0.117, p(90)=0.018, p(95)=0.029, p(99)=0.100
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: p(95)=0.004, p(99)=0.068, avg=0.004, min=0.000, med=0.000, max=0.084, p(90)=0.000
- http_req_sending: p(95)=0.078, p(99)=0.092, avg=0.057, min=0.041, med=0.051, max=0.095, p(90)=0.076
- iterations: count=20.000, rate=4.266
- http_req_duration: avg=33.211, min=13.391, med=34.242, max=55.071, p(90)=46.227, p(95)=52.553, p(99)=54.567
- http_req_waiting: p(90)=46.071, p(95)=52.356, p(99)=54.359, avg=33.062, min=13.294, med=34.133, max=54.860
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_receiving: avg=0.092, min=0.047, med=0.072, max=0.335, p(90)=0.137, p(95)=0.156, p(99)=0.299
- http_req_duration{expected_response:true}: max=55.071, p(90)=46.227, p(95)=52.553, p(99)=54.567, avg=33.211, min=13.391, med=34.242
